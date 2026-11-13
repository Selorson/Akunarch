use crate::db::akunarch_projects_root;
use crate::projects::{
    ensure_project_folder_tree, get_project_by_slug, list_projects, sanitize_project_slug,
    update_project_manifest_in_root, ProjectRecord,
};
use chrono::Utc;
use image::{ImageBuffer, Luma};
use rusqlite::Connection;
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::collections::HashMap;
use std::io::Write;
use std::path::{Path, PathBuf};
use zip::write::SimpleFileOptions;

pub const CHUNK_GRID_RES: usize = 65;
pub const CHUNK_WORLD_METERS: f64 = 256.0;

// ══════════════════════════════════════════════════════════════════════════════
// PHASE 2 — SEAMLESS 256m×256m OPEN-WORLD CHUNKS (`0.000m` EDGE-STITCHING)
// ══════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkStitchReport {
    pub slug: String,
    pub chunk_x: i32,
    pub chunk_z: i32,
    pub grid_resolution: usize,
    pub min_height_m: f32,
    pub max_height_m: f32,
    pub max_seam_error_m: f32,
    pub stitched_neighbors: Vec<String>,
    pub heightmap_png_path: String,
    pub project: ProjectRecord,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkPackResult {
    pub zip_path: String,
    pub size_bytes: u64,
    pub max_seam_error_m: f32,
    pub stitched_neighbors: Vec<String>,
    pub project: ProjectRecord,
}

fn hash2d(ix: i64, iz: i64, seed: u64) -> f64 {
    let mut h = (ix as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15)
        ^ (iz as u64).wrapping_mul(0xBF58_476D_1CE4_E5B9)
        ^ seed.wrapping_mul(0x94D0_49BB_1331_11EB);
    h = (h ^ (h >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    h = (h ^ (h >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    h ^= h >> 31;
    ((h >> 11) as f64) * (1.0 / ((1u64 << 53) as f64))
}

fn value_noise_2d(x: f64, z: f64, seed: u64) -> f64 {
    let x0 = x.floor() as i64;
    let z0 = z.floor() as i64;
    let fx = x - (x0 as f64);
    let fz = z - (z0 as f64);
    let ux = fx * fx * (3.0 - 2.0 * fx);
    let uz = fz * fz * (3.0 - 2.0 * fz);

    let n00 = hash2d(x0, z0, seed);
    let n10 = hash2d(x0 + 1, z0, seed);
    let n01 = hash2d(x0, z0 + 1, seed);
    let n11 = hash2d(x0 + 1, z0 + 1, seed);

    let nx0 = n00 + (n10 - n00) * ux;
    let nx1 = n01 + (n11 - n01) * ux;
    (nx0 + (nx1 - nx0) * uz) * 2.0 - 1.0
}

fn fbm_world(world_x: f64, world_z: f64, seed: u64) -> f64 {
    let mut sum = 0.0;
    let mut amp = 0.5;
    let mut freq = 1.0 / 160.0;
    for oct in 0..5u64 {
        sum += amp * value_noise_2d(world_x * freq, world_z * freq, seed + oct * 37);
        freq *= 2.03;
        amp *= 0.5;
    }
    sum
}

/// Deterministic continuous world-space terrain elevation in meters (`world_x`, `world_z`).
/// Because adjacent chunks evaluate exact shared world coordinates on their borders
/// (`0 * 256 + 128 == 1 * 256 - 128 == 128.0`), neighboring chunks match to `0.000m` natively.
pub fn sample_world_terrain_height(
    planet: &str,
    biome: &str,
    world_x: f64,
    world_z: f64,
    amplitude_scale: f64,
) -> f32 {
    let seed = if planet.eq_ignore_ascii_case("earth") {
        0xEA77_4101
    } else {
        0xA411_A71A
    };
    let b = biome.trim().to_ascii_lowercase();
    let (base_h, relief, ridge_gain) = if b.contains("mountain") || b.contains("highland") || b.contains("cliff") {
        (5.2, 22.0, 9.5)
    } else if b.contains("desert") || b.contains("sand") {
        (3.0, 8.5, 2.5)
    } else if b.contains("snow") || b.contains("tundra") {
        (4.5, 16.5, 6.5)
    } else if b.contains("basin") || b.contains("zyberon") || b.contains("crystal") {
        (3.8, 14.5, 5.2)
    } else {
        (3.4, 11.5, 4.0)
    };

    let macro_n = fbm_world(world_x, world_z, seed);
    let ridge_raw = 1.0 - fbm_world(world_x * 1.45 + 91.0, world_z * 1.45 - 47.0, seed ^ 0x55AA).abs();
    let ridge = ridge_raw * ridge_raw;

    // Gentle meandering river channel curving continuously across chunks [0,0] -> [1,0]
    let river_center_z = 26.0 * (world_x / 185.0).sin() - 18.0;
    let dist_river = (world_z - river_center_z).abs();
    let river_carve = (-((dist_river / 22.0).powi(2))).exp() * 4.8;

    let h = base_h + (macro_n * relief + ridge * ridge_gain) * amplitude_scale.clamp(0.25, 3.0) - river_carve;
    (h as f32).clamp(-4.0, 68.0)
}

pub fn build_raw_chunk_heightmap(
    planet: &str,
    biome: &str,
    chunk_x: i32,
    chunk_z: i32,
    amplitude_scale: f64,
) -> Vec<f32> {
    let res = CHUNK_GRID_RES;
    let step = CHUNK_WORLD_METERS / ((res - 1) as f64);
    let origin_x = (chunk_x as f64) * CHUNK_WORLD_METERS;
    let origin_z = (chunk_z as f64) * CHUNK_WORLD_METERS;
    let mut vals = Vec::with_capacity(res * res);

    for iz in 0..res {
        let local_z = -0.5 * CHUNK_WORLD_METERS + (iz as f64) * step;
        for ix in 0..res {
            let local_x = -0.5 * CHUNK_WORLD_METERS + (ix as f64) * step;
            let h = sample_world_terrain_height(
                planet,
                biome,
                origin_x + local_x,
                origin_z + local_z,
                amplitude_scale,
            );
            vals.push((h * 1000.0).round() / 1000.0);
        }
    }
    vals
}

pub fn write_heightmap_16bit_png(folder: &Path, values: &[f32], res: usize) -> Result<PathBuf, String> {
    if values.len() != res * res {
        return Err(format!(
            "Kích thước lưới heightmap không khớp ({} != {}×{}).",
            values.len(),
            res,
            res
        ));
    }
    let chunks_dir = folder.join("chunks");
    std::fs::create_dir_all(&chunks_dir)
        .map_err(|e| format!("Không tạo được thư mục chunks: {e}"))?;
    let out_png = chunks_dir.join("heightmap_16bit.png");

    // Map [-8.0m .. +72.0m] linearly to [0 .. 65535]
    let min_ref = -8.0f32;
    let span_ref = 80.0f32;
    let mut img: ImageBuffer<Luma<u16>, Vec<u16>> = ImageBuffer::new(res as u32, res as u32);
    for iz in 0..res {
        for ix in 0..res {
            let h = values[iz * res + ix];
            let norm = ((h - min_ref) / span_ref).clamp(0.0, 1.0);
            let q = (norm * 65535.0).round() as u16;
            img.put_pixel(ix as u32, iz as u32, Luma([q]));
        }
    }
    img.save(&out_png)
        .map_err(|e| format!("Không ghi được heightmap_16bit.png: {e}"))?;
    Ok(out_png)
}

fn feather_weight(cell_dist: usize, band: usize) -> f32 {
    if cell_dist >= band {
        return 0.0;
    }
    let t = (cell_dist as f32) / (band as f32);
    0.5 * (1.0 + (std::f32::consts::PI * t).cos())
}

fn blend_west_edge(grid: &mut [f32], res: usize, target_col: &[f32], band: usize) {
    for iz in 0..res {
        let cur_edge = grid[iz * res];
        let diff = target_col[iz] - cur_edge;
        grid[iz * res] = target_col[iz];
        for ix in 1..band.min(res) {
            let w = feather_weight(ix, band);
            grid[iz * res + ix] += diff * w;
        }
    }
}

fn blend_east_edge(grid: &mut [f32], res: usize, target_col: &[f32], band: usize) {
    let last = res - 1;
    for iz in 0..res {
        let cur_edge = grid[iz * res + last];
        let diff = target_col[iz] - cur_edge;
        grid[iz * res + last] = target_col[iz];
        for d in 1..band.min(res) {
            let ix = last - d;
            let w = feather_weight(d, band);
            grid[iz * res + ix] += diff * w;
        }
    }
}

fn blend_north_edge(grid: &mut [f32], res: usize, target_row: &[f32], band: usize) {
    for ix in 0..res {
        let cur_edge = grid[ix];
        let diff = target_row[ix] - cur_edge;
        grid[ix] = target_row[ix];
        for iz in 1..band.min(res) {
            let w = feather_weight(iz, band);
            grid[iz * res + ix] += diff * w;
        }
    }
}

fn blend_south_edge(grid: &mut [f32], res: usize, target_row: &[f32], band: usize) {
    let last = res - 1;
    for ix in 0..res {
        let cur_edge = grid[last * res + ix];
        let diff = target_row[ix] - cur_edge;
        grid[last * res + ix] = target_row[ix];
        for d in 1..band.min(res) {
            let iz = last - d;
            let w = feather_weight(d, band);
            grid[iz * res + ix] += diff * w;
        }
    }
}

/// Ensures `target_slug` has a valid `65×65` heightmap, stitches its 4 cardinal edges (`W/E/N/S`)
/// and shared corners with any existing adjacent `open_world` chunks on the same `planet`,
/// persists all modified neighbor manifests + 16-bit PNGs, and verifies `0.000m` seam error.
pub fn stitch_chunk_with_neighbors_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
) -> Result<ChunkStitchReport, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let all_projects = list_projects(conn)?;
    let target_proj = all_projects
        .iter()
        .find(|p| p.slug == clean_slug)
        .cloned()
        .ok_or_else(|| format!("Không tìm thấy dự án Chunk '{clean_slug}'."))?;

    let res = CHUNK_GRID_RES;
    let planet = target_proj.manifest.planet.clone();
    let cx = target_proj.manifest.chunk_x;
    let cz = target_proj.manifest.chunk_z;

    let mut cur_manifest = target_proj.manifest.clone();
    cur_manifest.chunks.grid_resolution = res;
    if cur_manifest.chunks.heightmap_values.len() != res * res {
        cur_manifest.chunks.heightmap_values =
            build_raw_chunk_heightmap(&planet, &cur_manifest.biome, cx, cz, 1.0);
    }

    let mut neighbor_map: HashMap<(i32, i32), ProjectRecord> = HashMap::new();
    for p in all_projects {
        if p.slug != clean_slug
            && p.manifest.kind == "open_world"
            && p.manifest.planet.eq_ignore_ascii_case(&planet)
        {
            neighbor_map.insert((p.manifest.chunk_x, p.manifest.chunk_z), p);
        }
    }

    let band = 6usize;
    let mut stitched_slugs: Vec<String> = Vec::new();
    let mut updated_neighbors: Vec<(String, crate::projects::ProjectManifest)> = Vec::new();

    // 1. West neighbor `[cx - 1, cz]`: its East column (`ix = res - 1`) == our West column (`ix = 0`)
    if let Some(nb) = neighbor_map.get(&(cx - 1, cz)) {
        let mut nb_m = nb.manifest.clone();
        nb_m.chunks.grid_resolution = res;
        if nb_m.chunks.heightmap_values.len() != res * res {
            nb_m.chunks.heightmap_values =
                build_raw_chunk_heightmap(&planet, &nb_m.biome, cx - 1, cz, 1.0);
        }
        let shared: Vec<f32> = (0..res)
            .map(|iz| {
                0.5 * (cur_manifest.chunks.heightmap_values[iz * res]
                    + nb_m.chunks.heightmap_values[iz * res + (res - 1)])
            })
            .collect();
        blend_west_edge(&mut cur_manifest.chunks.heightmap_values, res, &shared, band);
        blend_east_edge(&mut nb_m.chunks.heightmap_values, res, &shared, band);
        stitched_slugs.push(nb.slug.clone());
        updated_neighbors.push((nb.slug.clone(), nb_m));
    }

    // 2. East neighbor `[cx + 1, cz]`: its West column (`ix = 0`) == our East column (`ix = res - 1`)
    if let Some(nb) = neighbor_map.get(&(cx + 1, cz)) {
        let mut nb_m = nb.manifest.clone();
        nb_m.chunks.grid_resolution = res;
        if nb_m.chunks.heightmap_values.len() != res * res {
            nb_m.chunks.heightmap_values =
                build_raw_chunk_heightmap(&planet, &nb_m.biome, cx + 1, cz, 1.0);
        }
        let shared: Vec<f32> = (0..res)
            .map(|iz| {
                0.5 * (cur_manifest.chunks.heightmap_values[iz * res + (res - 1)]
                    + nb_m.chunks.heightmap_values[iz * res])
            })
            .collect();
        blend_east_edge(&mut cur_manifest.chunks.heightmap_values, res, &shared, band);
        blend_west_edge(&mut nb_m.chunks.heightmap_values, res, &shared, band);
        stitched_slugs.push(nb.slug.clone());
        updated_neighbors.push((nb.slug.clone(), nb_m));
    }

    // 3. North neighbor `[cx, cz - 1]`: its South row (`iz = res - 1`) == our North row (`iz = 0`)
    if let Some(nb) = neighbor_map.get(&(cx, cz - 1)) {
        let mut nb_m = nb.manifest.clone();
        nb_m.chunks.grid_resolution = res;
        if nb_m.chunks.heightmap_values.len() != res * res {
            nb_m.chunks.heightmap_values =
                build_raw_chunk_heightmap(&planet, &nb_m.biome, cx, cz - 1, 1.0);
        }
        let shared: Vec<f32> = (0..res)
            .map(|ix| {
                0.5 * (cur_manifest.chunks.heightmap_values[ix]
                    + nb_m.chunks.heightmap_values[(res - 1) * res + ix])
            })
            .collect();
        blend_north_edge(&mut cur_manifest.chunks.heightmap_values, res, &shared, band);
        blend_south_edge(&mut nb_m.chunks.heightmap_values, res, &shared, band);
        stitched_slugs.push(nb.slug.clone());
        updated_neighbors.push((nb.slug.clone(), nb_m));
    }

    // 4. South neighbor `[cx, cz + 1]`: its North row (`iz = 0`) == our South row (`iz = res - 1`)
    if let Some(nb) = neighbor_map.get(&(cx, cz + 1)) {
        let mut nb_m = nb.manifest.clone();
        nb_m.chunks.grid_resolution = res;
        if nb_m.chunks.heightmap_values.len() != res * res {
            nb_m.chunks.heightmap_values =
                build_raw_chunk_heightmap(&planet, &nb_m.biome, cx, cz + 1, 1.0);
        }
        let shared: Vec<f32> = (0..res)
            .map(|ix| {
                0.5 * (cur_manifest.chunks.heightmap_values[(res - 1) * res + ix]
                    + nb_m.chunks.heightmap_values[ix])
            })
            .collect();
        blend_south_edge(&mut cur_manifest.chunks.heightmap_values, res, &shared, band);
        blend_north_edge(&mut nb_m.chunks.heightmap_values, res, &shared, band);
        stitched_slugs.push(nb.slug.clone());
        updated_neighbors.push((nb.slug.clone(), nb_m));
    }

    // Re-lock exact border equality on East/West after North/South pass so corners are 100% bit-identical
    for (nb_slug, nb_m) in &mut updated_neighbors {
        if nb_m.chunk_x == cx - 1 && nb_m.chunk_z == cz {
            for iz in 0..res {
                nb_m.chunks.heightmap_values[iz * res + (res - 1)] =
                    cur_manifest.chunks.heightmap_values[iz * res];
            }
        } else if nb_m.chunk_x == cx + 1 && nb_m.chunk_z == cz {
            for iz in 0..res {
                nb_m.chunks.heightmap_values[iz * res] =
                    cur_manifest.chunks.heightmap_values[iz * res + (res - 1)];
            }
        } else if nb_m.chunk_x == cx && nb_m.chunk_z == cz - 1 {
            for ix in 0..res {
                nb_m.chunks.heightmap_values[(res - 1) * res + ix] =
                    cur_manifest.chunks.heightmap_values[ix];
            }
        } else if nb_m.chunk_x == cx && nb_m.chunk_z == cz + 1 {
            for ix in 0..res {
                nb_m.chunks.heightmap_values[ix] =
                    cur_manifest.chunks.heightmap_values[(res - 1) * res + ix];
            }
        }
        let nb_folder = ensure_project_folder_tree(projects_root, nb_slug)?;
        let nb_png = write_heightmap_16bit_png(&nb_folder, &nb_m.chunks.heightmap_values, res)?;
        nb_m.chunks.heightmap_path = Some(nb_png.to_string_lossy().to_string());
        let _ = update_project_manifest_in_root(conn, projects_root, Some(nb_slug), nb_m)?;
    }

    // Compute exact seam error across all updated cardinal neighbors
    let mut max_seam_err = 0.0f32;
    for (_, nb_m) in &updated_neighbors {
        if nb_m.chunk_x == cx - 1 && nb_m.chunk_z == cz {
            for iz in 0..res {
                let d = (cur_manifest.chunks.heightmap_values[iz * res]
                    - nb_m.chunks.heightmap_values[iz * res + (res - 1)])
                .abs();
                max_seam_err = max_seam_err.max(d);
            }
        } else if nb_m.chunk_x == cx + 1 && nb_m.chunk_z == cz {
            for iz in 0..res {
                let d = (cur_manifest.chunks.heightmap_values[iz * res + (res - 1)]
                    - nb_m.chunks.heightmap_values[iz * res])
                .abs();
                max_seam_err = max_seam_err.max(d);
            }
        } else if nb_m.chunk_x == cx && nb_m.chunk_z == cz - 1 {
            for ix in 0..res {
                let d = (cur_manifest.chunks.heightmap_values[ix]
                    - nb_m.chunks.heightmap_values[(res - 1) * res + ix])
                .abs();
                max_seam_err = max_seam_err.max(d);
            }
        } else if nb_m.chunk_x == cx && nb_m.chunk_z == cz + 1 {
            for ix in 0..res {
                let d = (cur_manifest.chunks.heightmap_values[(res - 1) * res + ix]
                    - nb_m.chunks.heightmap_values[ix])
                .abs();
                max_seam_err = max_seam_err.max(d);
            }
        }
    }

    let folder = ensure_project_folder_tree(projects_root, &clean_slug)?;
    let png_path = write_heightmap_16bit_png(&folder, &cur_manifest.chunks.heightmap_values, res)?;
    cur_manifest.chunks.heightmap_path = Some(png_path.to_string_lossy().to_string());

    let mut min_h = f32::MAX;
    let mut max_h = f32::MIN;
    for &v in &cur_manifest.chunks.heightmap_values {
        min_h = min_h.min(v);
        max_h = max_h.max(v);
    }

    let saved = update_project_manifest_in_root(conn, projects_root, Some(&clean_slug), &mut cur_manifest)?;
    Ok(ChunkStitchReport {
        slug: saved.slug.clone(),
        chunk_x: cx,
        chunk_z: cz,
        grid_resolution: res,
        min_height_m: min_h,
        max_height_m: max_h,
        max_seam_error_m: max_seam_err,
        stitched_neighbors: stitched_slugs,
        heightmap_png_path: png_path.to_string_lossy().to_string(),
        project: saved,
    })
}

pub fn generate_chunk_terrain(
    conn: &Connection,
    slug: &str,
    biome_override: Option<&str>,
    amplitude_scale: Option<f64>,
) -> Result<ChunkStitchReport, String> {
    generate_chunk_terrain_in_root(
        conn,
        &akunarch_projects_root(),
        slug,
        biome_override,
        amplitude_scale,
    )
}

pub fn generate_chunk_terrain_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
    biome_override: Option<&str>,
    amplitude_scale: Option<f64>,
) -> Result<ChunkStitchReport, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let mut proj = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;

    if let Some(b) = biome_override.map(str::trim).filter(|s| !s.is_empty()) {
        proj.manifest.biome = b.to_string();
    }
    proj.manifest.chunks.grid_resolution = CHUNK_GRID_RES;
    proj.manifest.chunks.heightmap_values = build_raw_chunk_heightmap(
        &proj.manifest.planet,
        &proj.manifest.biome,
        proj.manifest.chunk_x,
        proj.manifest.chunk_z,
        amplitude_scale.unwrap_or(1.0),
    );
    let _ = update_project_manifest_in_root(conn, projects_root, Some(&clean_slug), &mut proj.manifest)?;
    stitch_chunk_with_neighbors_in_root(conn, projects_root, &clean_slug)
}

pub fn sculpt_chunk_terrain(
    conn: &Connection,
    slug: &str,
    local_x: f64,
    local_z: f64,
    radius_m: f64,
    strength_or_target: f32,
    brush_mode: &str,
) -> Result<ChunkStitchReport, String> {
    sculpt_chunk_terrain_in_root(
        conn,
        &akunarch_projects_root(),
        slug,
        local_x,
        local_z,
        radius_m,
        strength_or_target,
        brush_mode,
    )
}

pub fn sculpt_chunk_terrain_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
    local_x: f64,
    local_z: f64,
    radius_m: f64,
    strength_or_target: f32,
    brush_mode: &str,
) -> Result<ChunkStitchReport, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let mut proj = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;
    let res = CHUNK_GRID_RES;
    if proj.manifest.chunks.heightmap_values.len() != res * res {
        proj.manifest.chunks.heightmap_values = build_raw_chunk_heightmap(
            &proj.manifest.planet,
            &proj.manifest.biome,
            proj.manifest.chunk_x,
            proj.manifest.chunk_z,
            1.0,
        );
    }

    let r = radius_m.clamp(4.0, 120.0);
    let step = CHUNK_WORLD_METERS / ((res - 1) as f64);
    let snapshot = proj.manifest.chunks.heightmap_values.clone();

    for iz in 0..res {
        let vz = -0.5 * CHUNK_WORLD_METERS + (iz as f64) * step;
        for ix in 0..res {
            let vx = -0.5 * CHUNK_WORLD_METERS + (ix as f64) * step;
            let dist = ((vx - local_x).powi(2) + (vz - local_z).powi(2)).sqrt();
            if dist > r {
                continue;
            }
            let t = (dist / r) as f32;
            let falloff = 0.5 * (1.0 + (std::f32::consts::PI * t).cos());
            let idx = iz * res + ix;
            let cur = proj.manifest.chunks.heightmap_values[idx];
            let next = match brush_mode.trim().to_ascii_lowercase().as_str() {
                "lower" => cur - strength_or_target.abs() * falloff,
                "flatten" => cur + (strength_or_target - cur) * falloff * 0.85,
                "smooth" => {
                    let mut acc = 0.0f32;
                    let mut cnt = 0usize;
                    for dz in -1isize..=1 {
                        for dx in -1isize..=1 {
                            let nx = (ix as isize + dx).clamp(0, (res - 1) as isize) as usize;
                            let nz = (iz as isize + dz).clamp(0, (res - 1) as isize) as usize;
                            acc += snapshot[nz * res + nx];
                            cnt += 1;
                        }
                    }
                    let avg = acc / (cnt as f32);
                    cur + (avg - cur) * falloff * 0.75
                }
                _ => cur + strength_or_target.abs() * falloff,
            };
            proj.manifest.chunks.heightmap_values[idx] =
                ((next.clamp(-6.0, 70.0)) * 1000.0).round() / 1000.0;
        }
    }

    let _ = update_project_manifest_in_root(conn, projects_root, Some(&clean_slug), &mut proj.manifest)?;
    stitch_chunk_with_neighbors_in_root(conn, projects_root, &clean_slug)
}

pub fn pack_chunk_zip(conn: &Connection, slug: &str) -> Result<ChunkPackResult, String> {
    pack_chunk_zip_in_root(conn, &akunarch_projects_root(), slug)
}

pub fn pack_chunk_zip_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
) -> Result<ChunkPackResult, String> {
    let stitch_rep = stitch_chunk_with_neighbors_in_root(conn, projects_root, slug)?;
    let mut proj = stitch_rep.project;
    let folder = PathBuf::from(&proj.folder_path);
    let chunks_dir = folder.join("chunks");
    std::fs::create_dir_all(&chunks_dir)
        .map_err(|e| format!("Không tạo được thư mục chunks: {e}"))?;

    let zip_name = format!(
        "chunk_{}_{}_{}.zip",
        proj.manifest.planet, proj.manifest.chunk_x, proj.manifest.chunk_z
    );
    let out_zip = chunks_dir.join(&zip_name);
    let file = std::fs::File::create(&out_zip)
        .map_err(|e| format!("Không tạo được {}: {e}", out_zip.display()))?;
    let mut zip = zip::ZipWriter::new(file);
    let opts = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);

    // 1. Heightmap 16-bit PNG
    let hm_png = Path::new(&stitch_rep.heightmap_png_path);
    if hm_png.is_file() {
        if let Ok(bytes) = std::fs::read(hm_png) {
            zip.start_file("heightmap_16bit.png", opts)
                .map_err(|e| e.to_string())?;
            zip.write_all(&bytes).map_err(|e| e.to_string())?;
        }
    }

    // 2. Optional 3D Gaussian Splat (.ply / .spz)
    let mut splat_archive_rel: Option<String> = None;
    if let Some(sp) = proj.manifest.chunks.splat_path.as_deref() {
        let p = Path::new(sp.trim());
        if p.is_file() {
            if let Ok(bytes) = std::fs::read(p) {
                let fname = p
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("scene_splat.ply");
                let rel = format!("splat/{fname}");
                zip.start_file(&rel, opts).map_err(|e| e.to_string())?;
                zip.write_all(&bytes).map_err(|e| e.to_string())?;
                splat_archive_rel = Some(rel);
            }
        }
    }

    // 3. Ambient Audio Zones files
    let mut bundled_audio_zones = Vec::new();
    for (idx, az) in proj.manifest.chunks.audio_zones.iter().enumerate() {
        let p = Path::new(az.audio_path.trim());
        let mut archive_audio = None;
        if p.is_file() {
            if let Ok(bytes) = std::fs::read(p) {
                let ext = p.extension().and_then(|e| e.to_str()).unwrap_or("wav");
                let rel = format!("audio/zone_{idx:02}_{}.{ext}", sanitize_project_slug(&az.id).unwrap_or_else(|_| format!("z{idx}")));
                let _ = zip.start_file(&rel, opts);
                let _ = zip.write_all(&bytes);
                archive_audio = Some(rel);
            }
        }
        bundled_audio_zones.push(json!({
            "id": az.id,
            "label": az.label,
            "x": az.x,
            "z": az.z,
            "radius": az.radius,
            "volume": az.volume,
            "archive_path": archive_audio,
            "local_audio_path": az.audio_path,
        }));
    }

    // 4. Chunk manifest inside archive
    let chunk_manifest = json!({
        "format": "akunarch.chunk/2.1",
        "exported_at": Utc::now().to_rfc3339(),
        "slug": proj.slug,
        "title": proj.manifest.title,
        "title_en": proj.manifest.title_en,
        "planet": proj.manifest.planet,
        "region_slug": proj.manifest.region_slug,
        "biome": proj.manifest.biome,
        "chunk_x": proj.manifest.chunk_x,
        "chunk_z": proj.manifest.chunk_z,
        "world_size": proj.manifest.world_size,
        "grid_resolution": proj.manifest.chunks.grid_resolution,
        "water_level": proj.manifest.chunks.water_level,
        "foliage_density": proj.manifest.chunks.foliage_density,
        "max_seam_error_m": stitch_rep.max_seam_error_m,
        "stitched_neighbors": stitch_rep.stitched_neighbors,
        "splat_archive_path": splat_archive_rel,
        "heightmap_values": proj.manifest.chunks.heightmap_values,
        "placements": proj.manifest.chunks.placements,
        "audio_zones": bundled_audio_zones,
        "spawn_points": proj.manifest.chunks.spawn_points,
        "vn_triggers": proj.manifest.chunks.vn_triggers,
    });
    let manifest_bytes = serde_json::to_vec_pretty(&chunk_manifest)
        .map_err(|e| format!("Lỗi tuần tự hóa chunk_manifest.json: {e}"))?;
    zip.start_file("chunk_manifest.json", opts)
        .map_err(|e| e.to_string())?;
    zip.write_all(&manifest_bytes).map_err(|e| e.to_string())?;
    let _ = std::fs::write(chunks_dir.join("chunk_manifest.json"), &manifest_bytes);

    zip.finish()
        .map_err(|e| format!("Lỗi đóng gói {zip_name}: {e}"))?;

    let size_bytes = std::fs::metadata(&out_zip).map(|m| m.len()).unwrap_or(0);
    let zip_str = out_zip.to_string_lossy().to_string();
    proj.manifest.chunks.pack_zip_path = Some(zip_str.clone());
    let updated = update_project_manifest_in_root(
        conn,
        projects_root,
        Some(&proj.slug.clone()),
        &mut proj.manifest,
    )?;

    Ok(ChunkPackResult {
        zip_path: zip_str,
        size_bytes,
        max_seam_error_m: stitch_rep.max_seam_error_m,
        stitched_neighbors: stitch_rep.stitched_neighbors,
        project: updated,
    })
}

// ══════════════════════════════════════════════════════════════════════════════
// PHASE 3 — 3D VISUAL NOVEL STAGE (`episode.json` + `vn_episode_<slug>.zip`)
// ══════════════════════════════════════════════════════════════════════════════

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnCameraRig {
    #[serde(default = "default_vn_rig_preset")]
    pub preset: String,
    #[serde(default = "default_vn_fov")]
    pub fov_deg: f64,
    #[serde(default = "default_vn_pos")]
    pub pos: [f64; 3],
    #[serde(default = "default_vn_target")]
    pub target: [f64; 3],
    #[serde(default = "default_vn_weather")]
    pub weather: String,
    #[serde(default = "default_vn_exposure")]
    pub exposure: f64,
    #[serde(default)]
    pub source_slug: Option<String>,
}

impl Default for VnCameraRig {
    fn default() -> Self {
        Self {
            preset: default_vn_rig_preset(),
            fov_deg: default_vn_fov(),
            pos: default_vn_pos(),
            target: default_vn_target(),
            weather: default_vn_weather(),
            exposure: default_vn_exposure(),
            source_slug: None,
        }
    }
}

fn default_vn_rig_preset() -> String {
    "eye_level_wide".to_string()
}
fn default_vn_fov() -> f64 {
    38.0
}
fn default_vn_pos() -> [f64; 3] {
    [0.0, 5.2, 16.5]
}
fn default_vn_target() -> [f64; 3] {
    [0.0, 3.0, 0.0]
}
fn default_vn_weather() -> String {
    "mist".to_string()
}
fn default_vn_exposure() -> f64 {
    1.08
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnCharacterCast {
    pub id: String,
    pub name_vi: String,
    pub name_en: String,
    #[serde(default = "default_vi_voice")]
    pub voice_vi: String,
    #[serde(default = "default_en_voice")]
    pub voice_en: String,
    #[serde(default)]
    pub portrait_path: Option<String>,
    #[serde(default = "default_cast_color")]
    pub accent_color: String,
}

fn default_vi_voice() -> String {
    "Thùy Dung".to_string()
}
fn default_en_voice() -> String {
    "female".to_string()
}
fn default_cast_color() -> String {
    "#6ee7b7".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnHotspot {
    pub id: String,
    pub x_pct: f64,
    pub y_pct: f64,
    pub label_vi: String,
    pub label_en: String,
    pub inspect_vi: String,
    pub inspect_en: String,
    #[serde(default)]
    pub unlock_tip_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnChoiceOption {
    pub id: String,
    pub label_vi: String,
    pub label_en: String,
    pub target_node_id: String,
    #[serde(default)]
    pub grant_shard_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnDialogueNode {
    pub id: String,
    pub speaker_id: String,
    #[serde(default = "default_expression")]
    pub expression: String,
    pub text_vi: String,
    pub text_en: String,
    #[serde(default)]
    pub backdrop_path: Option<String>,
    #[serde(default)]
    pub voice_vi_path: Option<String>,
    #[serde(default)]
    pub voice_en_path: Option<String>,
    #[serde(default)]
    pub bgm_override_path: Option<String>,
    #[serde(default)]
    pub next_node_id: Option<String>,
    #[serde(default)]
    pub choices: Vec<VnChoiceOption>,
    #[serde(default)]
    pub hotspots: Vec<VnHotspot>,
    #[serde(default)]
    pub unlock_tip_ids: Vec<String>,
    #[serde(default)]
    pub unlock_shard_id: Option<String>,
}

fn default_expression() -> String {
    "calm".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnTipEntry {
    pub id: String,
    pub term_vi: String,
    pub term_en: String,
    pub body_vi: String,
    pub body_en: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnMemoryShard {
    pub id: String,
    pub title_vi: String,
    pub title_en: String,
    pub echo_vi: String,
    pub echo_en: String,
    #[serde(default)]
    pub chapter_hint: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnEpisodeDocument {
    #[serde(default = "default_vn_schema")]
    pub schema_version: String,
    pub slug: String,
    pub title_vi: String,
    pub title_en: String,
    #[serde(default)]
    pub synopsis_vi: String,
    #[serde(default)]
    pub synopsis_en: String,
    pub entry_node_id: String,
    #[serde(default)]
    pub bgm_path: Option<String>,
    #[serde(default)]
    pub default_backdrop_path: Option<String>,
    #[serde(default)]
    pub camera_rig: VnCameraRig,
    #[serde(default)]
    pub cast: Vec<VnCharacterCast>,
    #[serde(default)]
    pub nodes: Vec<VnDialogueNode>,
    #[serde(default)]
    pub tips: Vec<VnTipEntry>,
    #[serde(default)]
    pub memory_shards: Vec<VnMemoryShard>,
    /// Populated when packed into `vn_episode_<slug>.zip` so `VNScenePlayer` resolves bundled files cleanly
    #[serde(default)]
    pub archive_asset_map: HashMap<String, String>,
}

fn default_vn_schema() -> String {
    "1.0".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnLintIssue {
    pub severity: String, // "blocker" | "warning"
    pub rule_code: String,
    pub location: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnSaveResult {
    pub episode: VnEpisodeDocument,
    pub lint_issues: Vec<VnLintIssue>,
    pub project: ProjectRecord,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VnPackResult {
    pub zip_path: String,
    pub size_bytes: u64,
    pub bundled_files_count: usize,
    pub lint_issues: Vec<VnLintIssue>,
    pub project: ProjectRecord,
}

fn has_standalone_word_vi(text_lower: &str, target: &str) -> bool {
    let mut from = 0;
    while let Some(rel) = text_lower[from..].find(target) {
        let start = from + rel;
        let end = start + target.len();
        let prev_ok = text_lower[..start]
            .chars()
            .next_back()
            .is_none_or(|c| !c.is_alphanumeric());
        let next_ok = text_lower[end..]
            .chars()
            .next()
            .is_none_or(|c| !c.is_alphanumeric());
        if prev_ok && next_ok {
            return true;
        }
        from = start + target.chars().next().map_or(1, char::len_utf8);
    }
    false
}

/// Strictly validates Visual Novel prose against Ecosystem Rule #36 (Southern Vietnamese dialect,
/// zero polite particle `"ạ"`, zero em-dash `—` in narrative/dialogue) and Rule #34 (Subtext Only,
/// zero modern physics jargon, zero external philosopher/author names).
pub fn lint_vn_episode_prose(ep: &VnEpisodeDocument) -> Vec<VnLintIssue> {
    let mut issues = Vec::new();

    let check_pair = |loc: &str, vi: &str, en: &str, out: &mut Vec<VnLintIssue>| {
        let vi_lower = vi.to_lowercase();
        let both_lower = format!("{vi_lower}\n{}", en.to_lowercase());

        if vi.contains('—') {
            out.push(VnLintIssue {
                severity: "blocker".into(),
                rule_code: "RULE_36_NO_EM_DASH".into(),
                location: loc.to_string(),
                message: format!("Cấm dùng dấu gạch ngang dài '—' trong văn xuôi/lời thoại ({loc}). Hãy dùng dấu phẩy hoặc ngắt câu tự nhiên."),
            });
        }
        if has_standalone_word_vi(&vi_lower, "ạ") {
            out.push(VnLintIssue {
                severity: "blocker".into(),
                rule_code: "RULE_36_NO_PARTICLE_A".into(),
                location: loc.to_string(),
                message: format!("Vi phạm Rule #36 (Phương ngữ Nam Bộ): cấm dùng trợ từ 'ạ' trong lời thoại ({loc}). Hãy dùng 'dạ', 'nghen', 'hen', 'đa'."),
            });
        }

        for northern in [
            "bát cháo", "cái bát", "cái thìa", "cái cốc", "cái ô", "quả trứng", "cái đĩa",
            "cái chăn", "cái đệm", "lúc nãy",
        ] {
            if has_standalone_word_vi(&vi_lower, northern) {
                out.push(VnLintIssue {
                    severity: "warning".into(),
                    rule_code: "RULE_36_SOUTHERN_LEXICON".into(),
                    location: loc.to_string(),
                    message: format!("Gợi ý Rule #36 tại {loc}: nên đổi '{northern}' sang từ vựng miền Nam chuẩn."),
                });
            }
        }

        for modern_or_external in [
            "lượng tử",
            "quantum",
            "entropy",
            "thuyết tương đối",
            "relativity",
            "nhiệt động lực học",
            "thermodynamics",
            "không-thời gian",
            "spacetime",
            "wavefunction",
            "photon",
            "nanometer",
            "nietzsche",
            "dostoevsky",
            "kant",
            "kantian",
            "rawls",
            "trang tử",
            "khổng tử",
            "steins;gate",
        ] {
            if has_standalone_word_vi(&both_lower, modern_or_external) {
                out.push(VnLintIssue {
                    severity: "blocker".into(),
                    rule_code: "RULE_34_SUBTEXT_ONLY".into(),
                    location: loc.to_string(),
                    message: format!(
                        "Vi phạm Rule #34 (Subtext Only) tại {loc}: cấm dùng thuật ngữ vật lý hiện đại hoặc tên riêng ngoại lai '{modern_or_external}'."
                    ),
                });
            }
        }
    };

    check_pair("synopsis", &ep.synopsis_vi, &ep.synopsis_en, &mut issues);

    for node in &ep.nodes {
        check_pair(&format!("node:{}", node.id), &node.text_vi, &node.text_en, &mut issues);
        for ch in &node.choices {
            check_pair(
                &format!("choice:{}:{}", node.id, ch.id),
                &ch.label_vi,
                &ch.label_en,
                &mut issues,
            );
        }
        for hs in &node.hotspots {
            check_pair(
                &format!("hotspot:{}:{}", node.id, hs.id),
                &hs.inspect_vi,
                &hs.inspect_en,
                &mut issues,
            );
        }
    }

    for tip in &ep.tips {
        check_pair(&format!("tip:{}", tip.id), &tip.body_vi, &tip.body_en, &mut issues);
    }
    for sh in &ep.memory_shards {
        check_pair(&format!("shard:{}", sh.id), &sh.echo_vi, &sh.echo_en, &mut issues);
    }

    issues
}

pub fn default_starter_vn_episode(proj: &ProjectRecord) -> VnEpisodeDocument {
    let backdrop = proj
        .manifest
        .manga_plates
        .first()
        .map(|p| p.beauty_path.clone())
        .or_else(|| proj.manifest.local_image_path.clone())
        .or_else(|| proj.manifest.concept_paths.first().cloned());

    VnEpisodeDocument {
        schema_version: "1.0".into(),
        slug: proj.slug.clone(),
        title_vi: if proj.manifest.title.trim().is_empty() {
            "Tiếng Vọng Dưới Mái Vòm Cổ".into()
        } else {
            proj.manifest.title.clone()
        },
        title_en: if proj.manifest.title_en.trim().is_empty() {
            "Echoes Beneath the Ancient Vault".into()
        } else {
            proj.manifest.title_en.clone()
        },
        synopsis_vi: "Hồi sương sớm còn giăng ngang bậc đá rêu, hai lữ khách dừng chân trước cỗ bánh răng đồng xanh đang rầm rì thức giấc.".into(),
        synopsis_en: "While morning mist still drifts across the mossy steps, two travelers pause before the bronze gearwork humming awake.".into(),
        entry_node_id: "n01_arrival".into(),
        bgm_path: proj.manifest.bgm_audio_path.clone(),
        default_backdrop_path: backdrop.clone(),
        camera_rig: VnCameraRig {
            preset: "low_angle_monument".into(),
            fov_deg: 36.0,
            pos: [0.0, 4.8, 15.2],
            target: [0.0, 3.4, 0.0],
            weather: "mist".into(),
            exposure: 1.08,
            source_slug: Some(proj.slug.clone()),
        },
        cast: vec![
            VnCharacterCast {
                id: "narrator".into(),
                name_vi: "Lời Dẫn".into(),
                name_en: "Narrator".into(),
                voice_vi: "Mỹ Duyên".into(),
                voice_en: "narrator".into(),
                portrait_path: None,
                accent_color: "#94a3b8".into(),
            },
            VnCharacterCast {
                id: "lyra".into(),
                name_vi: "Người Giữ Tháp".into(),
                name_en: "Spire Keeper".into(),
                voice_vi: "Thùy Dung".into(),
                voice_en: "female".into(),
                portrait_path: None,
                accent_color: "#6ee7b7".into(),
            },
            VnCharacterCast {
                id: "kael".into(),
                name_vi: "Lữ Khách Phương Nam".into(),
                name_en: "Southern Wayfarer".into(),
                voice_vi: "Minh Triết".into(),
                voice_en: "male".into(),
                portrait_path: None,
                accent_color: "#fbbf24".into(),
            },
        ],
        nodes: vec![
            VnDialogueNode {
                id: "n01_arrival".into(),
                speaker_id: "narrator".into(),
                expression: "solemn".into(),
                text_vi: "Gió sớm từ lòng chảo thổi ngược lên năm bậc thềm đá xám, mang theo mùi đồng cổ và hơi nước mát lạnh.".into(),
                text_en: "Morning wind rises from the basin up the five grey stone steps, carrying the scent of aged bronze and cool mist.".into(),
                backdrop_path: backdrop.clone(),
                voice_vi_path: None,
                voice_en_path: None,
                bgm_override_path: None,
                next_node_id: Some("n02_choice".into()),
                choices: vec![],
                hotspots: vec![VnHotspot {
                    id: "hs_astrolabe_ring".into(),
                    x_pct: 50.0,
                    y_pct: 42.0,
                    label_vi: "Vòng Khắc Cổ Ngữ Đồng Xanh".into(),
                    label_en: "Bronze Runic Astrolabe Ring".into(),
                    inspect_vi: "Vành đồng năm cạnh khắc khít từng nấc sao mùa nước nổi, chạm nhẹ vô vẫn nghe âm ngân trầm ấm.".into(),
                    inspect_en: "The five-sided bronze ring is etched with seasonal star notches, humming warmly at the lightest touch.".into(),
                    unlock_tip_id: Some("tip_fivefold_seal".into()),
                }],
                unlock_tip_ids: vec!["tip_fivefold_seal".into()],
                unlock_shard_id: None,
            },
            VnDialogueNode {
                id: "n02_choice".into(),
                speaker_id: "lyra".into(),
                expression: "focused".into(),
                text_vi: "Hồi nãy bánh răng tầng ngầm mới nhích thêm nửa khắc đó nghen. Mình bước vô soi bệ đá chính hay đi vòng ra hành lang gió trước đây?".into(),
                text_en: "Just moments ago the subterranean gear shifted another half-notch. Shall we inspect the central plinth or circle the wind gallery first?".into(),
                backdrop_path: backdrop.clone(),
                voice_vi_path: None,
                voice_en_path: None,
                bgm_override_path: None,
                next_node_id: None,
                choices: vec![
                    VnChoiceOption {
                        id: "ch_inspect_plinth".into(),
                        label_vi: "Đặt tay lên bệ đá trung tâm lắng nghe nhịp mạch ngầm".into(),
                        label_en: "Lay a hand on the central plinth to hear the subterranean pulse".into(),
                        target_node_id: "n03_plinth".into(),
                        grant_shard_id: Some("shard_emerald_echo".into()),
                    },
                    VnChoiceOption {
                        id: "ch_walk_gallery".into(),
                        label_vi: "Rẽ qua hành lang cột đá đón hướng nắng lên".into(),
                        label_en: "Step along the stone colonnade toward the rising sun".into(),
                        target_node_id: "n04_gallery".into(),
                        grant_shard_id: None,
                    },
                ],
                hotspots: vec![],
                unlock_tip_ids: vec![],
                unlock_shard_id: None,
            },
            VnDialogueNode {
                id: "n03_plinth".into(),
                speaker_id: "kael".into(),
                expression: "warm".into(),
                text_vi: "Dạ, nhịp đồng vọng lên đều đặn như tiếng nước lớn ngoài vàm sông vậy. Người xưa gầy dựng chốn này thiệt biết nương theo hơi thở của đất trời.".into(),
                text_en: "Indeed, the bronze cadence rises as steadily as high tide at a river mouth. Those who raised this sanctuary truly built in harmony with earth and sky.".into(),
                backdrop_path: backdrop.clone(),
                voice_vi_path: None,
                voice_en_path: None,
                bgm_override_path: None,
                next_node_id: None,
                choices: vec![],
                hotspots: vec![],
                unlock_tip_ids: vec![],
                unlock_shard_id: Some("shard_emerald_echo".into()),
            },
            VnDialogueNode {
                id: "n04_gallery".into(),
                speaker_id: "lyra".into(),
                expression: "calm".into(),
                text_vi: "Nhìn kìa, nắng đầu ngày vừa rọi xuyên vòm kính xanh ngọc, soi rõ con đường mòn dẫn sang sườn đồi bên kia luôn.".into(),
                text_en: "Look there, first daylight pierces the emerald glass dome, illuminating the trail across to the far hillside.".into(),
                backdrop_path: backdrop,
                voice_vi_path: None,
                voice_en_path: None,
                bgm_override_path: None,
                next_node_id: None,
                choices: vec![],
                hotspots: vec![],
                unlock_tip_ids: vec![],
                unlock_shard_id: None,
            },
        ],
        tips: vec![VnTipEntry {
            id: "tip_fivefold_seal".into(),
            term_vi: "Khóa Đồng Ngũ Giác".into(),
            term_en: "Pentagonal Bronze Lock".into(),
            body_vi: "Cơ cấu năm vành đồng lồng khít nhau không cần một đinh tán sắt nào, chỉ mở khi ánh bình minh rọi đúng rãnh dẫn nước trên mái vòm.".into(),
            body_en: "An interlocking assembly of five bronze rings built without a single iron rivet, opening only when dawn light aligns with the dome's water channels.".into(),
        }],
        memory_shards: vec![VnMemoryShard {
            id: "shard_emerald_echo".into(),
            title_vi: "Mảnh Ký Ức: Nhịp Mạch Đồng Xanh".into(),
            title_en: "Memory Shard: Verdigris Pulse".into(),
            echo_vi: "Tiếng ngân trầm dưới chân thềm nhắc rằng thánh tích chưa từng ngủ yên suốt ngàn năm gió cát.".into(),
            echo_en: "The deep resonance beneath the steps recalls that the sanctuary has never truly slumbered across a thousand years of wind.".into(),
            chapter_hint: Some(1),
        }],
        archive_asset_map: HashMap::new(),
    }
}

pub fn load_or_init_vn_episode(conn: &Connection, slug: &str) -> Result<VnEpisodeDocument, String> {
    load_or_init_vn_episode_in_root(conn, &akunarch_projects_root(), slug)
}

pub fn load_or_init_vn_episode_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
) -> Result<VnEpisodeDocument, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let proj = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;
    let folder = ensure_project_folder_tree(projects_root, &clean_slug)?;
    let ep_file = folder.join("stage_vn").join("episode.json");
    if ep_file.is_file() {
        let raw = std::fs::read_to_string(&ep_file)
            .map_err(|e| format!("Không đọc được {}: {e}", ep_file.display()))?;
        let parsed: VnEpisodeDocument = serde_json::from_str(&raw)
            .map_err(|e| format!("Lỗi cú pháp JSON trong episode.json: {e}"))?;
        return Ok(parsed);
    }
    let starter = default_starter_vn_episode(&proj);
    let pretty = serde_json::to_string_pretty(&starter).map_err(|e| e.to_string())?;
    std::fs::write(&ep_file, format!("{pretty}\n"))
        .map_err(|e| format!("Không ghi được {}: {e}", ep_file.display()))?;
    Ok(starter)
}

pub fn save_vn_episode(
    conn: &Connection,
    slug: &str,
    episode: VnEpisodeDocument,
) -> Result<VnSaveResult, String> {
    save_vn_episode_in_root(conn, &akunarch_projects_root(), slug, episode)
}

pub fn save_vn_episode_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
    mut episode: VnEpisodeDocument,
) -> Result<VnSaveResult, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let mut proj = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;
    let folder = ensure_project_folder_tree(projects_root, &clean_slug)?;
    let stage_dir = folder.join("stage_vn");
    std::fs::create_dir_all(&stage_dir).map_err(|e| e.to_string())?;

    episode.slug = clean_slug.clone();
    let lint_issues = lint_vn_episode_prose(&episode);

    let ep_file = stage_dir.join("episode.json");
    let pretty = serde_json::to_string_pretty(&episode).map_err(|e| e.to_string())?;
    std::fs::write(&ep_file, format!("{pretty}\n"))
        .map_err(|e| format!("Không ghi được {}: {e}", ep_file.display()))?;

    proj.manifest.stage_vn.episode_json_path = Some(ep_file.to_string_lossy().to_string());
    if !episode.title_vi.trim().is_empty() {
        proj.manifest.stage_vn.episode_title = Some(episode.title_vi.trim().to_string());
    }
    let updated = update_project_manifest_in_root(
        conn,
        projects_root,
        Some(&clean_slug),
        &mut proj.manifest,
    )?;

    Ok(VnSaveResult {
        episode,
        lint_issues,
        project: updated,
    })
}

pub fn pack_vn_episode_zip(conn: &Connection, slug: &str) -> Result<VnPackResult, String> {
    pack_vn_episode_zip_in_root(conn, &akunarch_projects_root(), slug)
}

pub fn pack_vn_episode_zip_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
) -> Result<VnPackResult, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let mut episode = load_or_init_vn_episode_in_root(conn, projects_root, &clean_slug)?;
    let lint_issues = lint_vn_episode_prose(&episode);
    if let Some(blocker) = lint_issues.iter().find(|i| i.severity == "blocker") {
        return Err(format!(
            "Chặn đóng gói VN do vi phạm [{}]: {}",
            blocker.rule_code, blocker.message
        ));
    }

    let mut proj = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;
    let folder = ensure_project_folder_tree(projects_root, &clean_slug)?;
    let stage_dir = folder.join("stage_vn");
    let zip_path = stage_dir.join(format!("vn_episode_{clean_slug}.zip"));

    let file = std::fs::File::create(&zip_path)
        .map_err(|e| format!("Không tạo được {}: {e}", zip_path.display()))?;
    let mut zip = zip::ZipWriter::new(file);
    let opts = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);

    let mut asset_map: HashMap<String, String> = HashMap::new();
    let mut written_rel_paths: std::collections::HashSet<String> = std::collections::HashSet::new();

    let mut bundle_local_asset = |opt_path: &Option<String>, category: &str| -> Result<(), String> {
        let Some(raw) = opt_path.as_deref().map(str::trim).filter(|s| !s.is_empty()) else {
            return Ok(());
        };
        if asset_map.contains_key(raw) {
            return Ok(());
        }
        let p = Path::new(raw);
        if !p.is_file() {
            return Ok(());
        }
        let bytes = std::fs::read(p).map_err(|e| format!("Không đọc được {}: {e}", p.display()))?;
        let base_name = p
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("asset.bin");
        let mut rel = format!("{category}/{base_name}");
        let mut counter = 2usize;
        while written_rel_paths.contains(&rel) {
            let stem = p.file_stem().and_then(|s| s.to_str()).unwrap_or("asset");
            let ext = p.extension().and_then(|e| e.to_str()).unwrap_or("bin");
            rel = format!("{category}/{stem}_{counter}.{ext}");
            counter += 1;
        }
        zip.start_file(&rel, opts).map_err(|e| e.to_string())?;
        zip.write_all(&bytes).map_err(|e| e.to_string())?;
        written_rel_paths.insert(rel.clone());
        asset_map.insert(raw.to_string(), rel);
        Ok(())
    };

    bundle_local_asset(&episode.bgm_path, "bgm")?;
    bundle_local_asset(&episode.default_backdrop_path, "backdrops")?;
    for c in &episode.cast {
        bundle_local_asset(&c.portrait_path, "portraits")?;
    }
    for n in &episode.nodes {
        bundle_local_asset(&n.backdrop_path, "backdrops")?;
        bundle_local_asset(&n.voice_vi_path, "voices")?;
        bundle_local_asset(&n.voice_en_path, "voices")?;
        bundle_local_asset(&n.bgm_override_path, "bgm")?;
    }

    episode.archive_asset_map = asset_map;
    let ep_bytes = serde_json::to_vec_pretty(&episode).map_err(|e| e.to_string())?;
    zip.start_file("episode.json", opts)
        .map_err(|e| e.to_string())?;
    zip.write_all(&ep_bytes).map_err(|e| e.to_string())?;
    let _ = std::fs::write(stage_dir.join("episode.json"), &ep_bytes);

    zip.finish()
        .map_err(|e| format!("Lỗi hoàn tất vn_episode_{clean_slug}.zip: {e}"))?;

    let size_bytes = std::fs::metadata(&zip_path).map(|m| m.len()).unwrap_or(0);
    let zip_str = zip_path.to_string_lossy().to_string();
    proj.manifest.stage_vn.episode_zip_path = Some(zip_str.clone());
    proj.manifest.stage_vn.episode_json_path =
        Some(stage_dir.join("episode.json").to_string_lossy().to_string());
    proj.manifest.stage_vn.episode_title = Some(episode.title_vi.clone());

    let updated = update_project_manifest_in_root(
        conn,
        projects_root,
        Some(&clean_slug),
        &mut proj.manifest,
    )?;

    Ok(VnPackResult {
        zip_path: zip_str,
        size_bytes,
        bundled_files_count: written_rel_paths.len(),
        lint_issues,
        project: updated,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::init_schema;
    use crate::projects::{create_project_in_root, CreateProjectInput};

    #[test]
    fn adjacent_open_world_chunks_stitch_with_exact_zero_seam_gap_and_export_zip() {
        let conn = Connection::open_in_memory().unwrap();
        init_schema(&conn).unwrap();
        let tmp_root = std::env::temp_dir().join(format!(
            "akunarch_chunk_stitch_test_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(11)
        ));

        for (slug, cx) in [("chunk-test-0-0", 0), ("chunk-test-1-0", 1)] {
            create_project_in_root(
                &conn,
                &tmp_root,
                CreateProjectInput {
                    slug: slug.into(),
                    title: format!("Ô Thử Nghiệm [{cx}, 0]"),
                    title_en: format!("Test Chunk [{cx}, 0]"),
                    kind: "open_world".into(),
                    planet: "akunalia".into(),
                    region_slug: "zyberon-basin".into(),
                    era: "".into(),
                    era_year: None,
                    lat: None,
                    lng: None,
                    biome: "zyberon-basin".into(),
                    chunk_x: cx,
                    chunk_z: 0,
                    cowriter_entity_id: None,
                    cowriter_key: "".into(),
                    unlock_chapter: Some(1),
                    description_vi: "Lòng chảo liền mạch.".into(),
                    description_en: "Seamless basin.".into(),
                    local_image_path: None,
                    concept_paths: vec![],
                    bgm_audio_path: None,
                    glb_path: None,
                },
            )
            .unwrap();
        }

        let _ = generate_chunk_terrain_in_root(&conn, &tmp_root, "chunk-test-0-0", None, Some(1.0))
            .unwrap();
        let _ = generate_chunk_terrain_in_root(&conn, &tmp_root, "chunk-test-1-0", None, Some(1.0))
            .unwrap();

        // Sculpt right near the shared East border (+120m) of [0,0] and verify neighbor [1,0] stitches to 0.000m!
        let sculpted = sculpt_chunk_terrain_in_root(
            &conn,
            &tmp_root,
            "chunk-test-0-0",
            120.0,
            10.0,
            28.0,
            6.5,
            "raise",
        )
        .unwrap();
        assert_eq!(
            sculpted.max_seam_error_m, 0.0,
            "adjacent chunks must have 0.000m seam gap after stitching"
        );
        assert!(sculpted
            .stitched_neighbors
            .contains(&"chunk-test-1-0".to_string()));

        let c0 = get_project_by_slug(&conn, "chunk-test-0-0").unwrap().unwrap();
        let c1 = get_project_by_slug(&conn, "chunk-test-1-0").unwrap().unwrap();
        let res = CHUNK_GRID_RES;
        for iz in 0..res {
            let east_of_0 = c0.manifest.chunks.heightmap_values[iz * res + (res - 1)];
            let west_of_1 = c1.manifest.chunks.heightmap_values[iz * res];
            assert_eq!(east_of_0, west_of_1, "seam vertex mismatch at row {iz}");
        }

        let packed = pack_chunk_zip_in_root(&conn, &tmp_root, "chunk-test-0-0").unwrap();
        assert!(Path::new(&packed.zip_path).is_file());
        assert!(packed.size_bytes > 512);

        let _ = std::fs::remove_dir_all(&tmp_root);
    }

    #[test]
    fn vn_episode_linter_enforces_rule36_and_rule34_and_packs_zip() {
        let conn = Connection::open_in_memory().unwrap();
        init_schema(&conn).unwrap();
        let tmp_root = std::env::temp_dir().join(format!(
            "akunarch_vn_pack_test_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(12)
        ));

        create_project_in_root(
            &conn,
            &tmp_root,
            CreateProjectInput {
                slug: "vn-test-sanctum".into(),
                title: "Tập VN Thử Nghiệm".into(),
                title_en: "Test VN Episode".into(),
                kind: "vn_episode".into(),
                planet: "akunalia".into(),
                region_slug: "zyberon".into(),
                era: "".into(),
                era_year: None,
                lat: None,
                lng: None,
                biome: "temperate".into(),
                chunk_x: 0,
                chunk_z: 0,
                cowriter_entity_id: None,
                cowriter_key: "".into(),
                unlock_chapter: Some(1),
                description_vi: "Trường quay kịch bản rẽ nhánh.".into(),
                description_en: "Branching VN stage.".into(),
                local_image_path: None,
                concept_paths: vec![],
                bgm_audio_path: None,
                glb_path: None,
            },
        )
        .unwrap();

        let starter =
            load_or_init_vn_episode_in_root(&conn, &tmp_root, "vn-test-sanctum").unwrap();
        let clean_issues = lint_vn_episode_prose(&starter);
        assert!(
            clean_issues.is_empty(),
            "starter Southern dialect VN script must have 0 lint issues: {clean_issues:?}"
        );

        let packed = pack_vn_episode_zip_in_root(&conn, &tmp_root, "vn-test-sanctum").unwrap();
        assert!(Path::new(&packed.zip_path).is_file());

        // Inject Rule #36 ("ạ" + em-dash) and Rule #34 ("quantum") violations -> must catch all 3!
        let mut bad = starter.clone();
        bad.nodes[0].text_vi = "Dạ vâng ạ — hiện tượng lượng tử này lạ quá.".into();
        bad.nodes[0].text_en = "This quantum wavefunction is strange.".into();
        let bad_issues = lint_vn_episode_prose(&bad);
        assert!(bad_issues.iter().any(|i| i.rule_code == "RULE_36_NO_EM_DASH"));
        assert!(bad_issues.iter().any(|i| i.rule_code == "RULE_36_NO_PARTICLE_A"));
        assert!(bad_issues.iter().any(|i| i.rule_code == "RULE_34_SUBTEXT_ONLY"));

        let _ = std::fs::remove_dir_all(&tmp_root);
    }
}
