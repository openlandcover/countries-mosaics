# Landsat Mosaics v2: what changed from version 1

A mosaic is one finished satellite image of one part of India for one
year, built by combining every usable Landsat picture taken that year.
The legacy product (version 1) was built with the MapBiomas method and
established this approach for India. Version 2 builds on it: most of
the design is inherited, and the changes below add cleaning steps, a
different year boundary, and a record of the evidence under every pixel.

Every row was checked against the code of both products, and every number against a recorded measurement. Numbers come
from one test cell in the Western Ghats (NC-43-X-D), so they show the
direction of a change, not a national guarantee. Improvements are
reported as reductions, not cures. The last column points to the section
of the ATBD that carries the detail and the evidence.

## 1. What goes into each image

| What is done | Version 1 | Version 2 | What this gains |
|---|---|---|---|
| **Years covered** | 1986–2025, calendar years. 1986 and 1987 are thin (images for 30 and 152 of the 283 cells). | 1986–2025, phenological years (section 3). | No extra years, and none lost. A check of the catalogue found no usable scenes for 1984 or 1985, so the series starts where the archive starts. *(ATBD 3.5)* |
| **Which satellites, and how they are combined** | One image per satellite per cell-year (a Landsat 5 image beside a Landsat 7 image); nothing in its code combines them. | One image per cell-year, pooling every satellite flying that year once they are matched (section 2). | One image to use, with more observations behind each pixel. *(ATBD 3.4, 5.7)* |
| **Which scenes are considered** | Scenes reported as 80% cloud or more are set aside whole. | Only near-total overcast (95% or more) is set aside; the rest is judged pixel by pixel. | Cloudy-season scenes can still contribute their clear parts. *(ATBD 5.1)* |
| **Striped Landsat 7** — its scanner failed in 2003, leaving blank stripes in every later scene | Its Landsat 7 images use every scene below the 80% cloud ceiling, stripes included. | After 2003, Landsat 7 is used only where, for a pixel and a three-month quarter, the healthy satellites gave fewer than three usable observations. | Stripe patterns are greatly reduced, not gone. In 2012, when only Landsat 7 flew, faint marks remain. *(ATBD 5.3, 10 L8)* |
| **Surface temperature layers** — new | None in the India images. | Three layers every year: the typical surface temperature, its spread, and the number of clear readings behind it. They come from a separate clear-sky record and receive no corrections. | Temperature is a useful signature of many land-cover types: bare ground, built land, water and irrigated fields all run at different temperatures. *(ATBD 5.11)* |

## 2. Cleaning the images

| What is done | Version 1 | Version 2 | What this gains |
|---|---|---|---|
| **Removing cloud and its shadow** | The cloud and shadow flags shipped with each Landsat scene. | The same flags, plus a temperature check and a brightness cut. | Two extra checks catch what the flags miss. Cloud is colder than the ground it hides, so each reading is compared with that pixel's usual clear-sky temperature; and unflagged cloud is bright, so readings far brighter in blue than the pixel's own year are dropped. Less cloud gets through in 33 of the 37 shared years; version 1 scores lower in 1989 and 1995. In the test cell, leftover cloud in the worst shared year fell from 23.5% to 9.5% of pixels, and is at or below 0.5% every year from 1999. Thin early years still carry some. *(ATBD 5.2, 9.4)* |
| **Terrain (hillside) illumination correction** — a sunlit slope reads bright and a shaded slope dark, for the same vegetation | Not applied. A slope layer is shipped. | The light each slope adds or takes away is worked out from physics (sun angle, slope, atmosphere) and divided out. The terrain itself is kept as separate layers. | On a test ridge, 57–80% of the gap between sunlit and shaded faces is closed. In steep wet forest the near-infrared over-corrects: a known leftover error. *(ATBD 5.4, 10 L9)* |
| **BRDF** (the correction for sun and viewing angles) — the same field reads brighter or darker depending on where the satellite and the sun stood | Not applied. | Every observation is moved to one standard sun-and-camera geometry, by a published method. | Brightness differences caused by the viewing angle are much reduced, so fewer of them read as change on the ground. *(ATBD 5.5)* |
| **Sensor harmonisation** — different instruments read the same ground slightly differently, so their readings are brought onto one common basis | No adjustment. Each satellite stays in its own image (section 1). | Landsat 5 and 7 readings converted onto the Landsat 8/9 basis: an India-derived conversion for Landsat 5, a published one for Landsat 7. | Keeping the satellites apart means any single series must change satellite between years with nothing to bridge the step. Version 2 removes it: in the test cell, no change of satellite left a step larger than ordinary year-to-year variation. *(ATBD 5.6, 9.3)* |

## 3. Summarising a year

| What is done | Version 1 | Version 2 | What this gains |
|---|---|---|---|
| **The year boundary** | The calendar year, 1 January to 31 December. | The phenological year, 1 April to 31 March, following the crop calendar. | India's winter crop is greenest in January–February. A calendar year cuts it in two; the pheno year keeps both crop seasons inside one image. *(ATBD 3.2)* |
| **Wet and dry summaries** — inherited | A wet and a dry summary for each pixel, from its own greenest and least-green quarter of observations, ranked by greenness (NDVI). | The same rule. One refinement: snow is left out of the ranking where a pixel has enough snow-free observations. | Version 1 already did this pixel by pixel. The snow refinement matters only in the Himalaya. *(ATBD 5.8)* |
| **How much a pixel varied within the year** | Four layers: the standard deviation, the amplitude (highest reading minus lowest), and the highest and lowest readings themselves. | Two layers: the MAD (median absolute deviation) for spread, and the swing, a signed greenest-minus-least-green difference. | All four version 1 layers rest on single extreme readings, so one stray cloud moves them, and all four were dropped. The MAD replaces the standard deviation: sort the year's readings, take the middle one, then the middle of the distances from it, so nothing at the edges can inflate it, and it assumes no bell-shaped year, which a farmed pixel does not have. The swing replaces the amplitude, both its ends being medians of a quarter of the year rather than single extremes. In the test cell version 1's spread rises to 0.11–0.12 in 2017, 2020 and 2022, version 2's stays within 0.08–0.10. *(ATBD 8.3, 9.2)* |
| **SMA (spectral mixture analysis) fractions** — each pixel's colour is split into shares of green vegetation, dry vegetation and soil, with shade as what is left | Each scene's shares have any negative value set to zero at once, then are stored as whole percentages. | Each scene's raw shares are kept, including values below zero. The year's statistics are worked out on them; the typical-value shares are clamped once at the end. | Clamping every scene cuts off one tail of the readings, which distorts any spread or seasonal difference built on them. Clamping once at the end keeps those statistics meaningful, and water reads as neutral rather than as an arbitrary value. *(ATBD 5.9)* |
| **NDFI over water and snow** — NDFI is a forest index built from the shares above | Reported everywhere, water and snow included. | A refusal code instead of a number over persistent water (−10) and over snow (−20). | NDFI is a land index, so over water and snow it returns numbers that look legal but mean nothing: measured over persistent water in the test cell, version 1 reads mostly zero or the neutral middle, with high values at the water's edge. A code cannot be mistaken for a reading, by a person or by a model. *(ATBD 6.6)* |

## 4. Knowing how much to trust each value

| What is done | Version 1 | Version 2 | What this gains |
|---|---|---|---|
| **Pixel-level reliability scoring** | Not included. | Count layers on every image: how many usable observations sit under each pixel, how many were snow, how many quarters of the year were seen, and the count for each quarter. | A user can judge, pixel by pixel, how much to trust a value. A thin early year says so itself. *(ATBD 6.5)* |
| **Extended metadata** — the documentation each image carries | Six labels: year, grid cell, satellite, version, territory, collection. | Twenty-six labels, including the decoding formula for every layer family, the satellites used, the number of passes, the start and end dates, and the exact code version that built it. | Anyone holding one image can decode it correctly and trace how it was made. *(ATBD 7)* |
| **The set of layers** — what each image contains | 119 layers: yearly, wet and dry typical values for six colour bands, eleven indices and six ground-component shares; a minimum, maximum, amplitude and standard deviation for many of them; a texture and a slope layer. | 117 layers: the same colour bands with their wet and dry values, the swing, the MAD, the ground-component shares, a smaller set of indices, surface temperature, terrain, position and the count layers. | Many layers were renamed, some dropped (texture, the minimum, maximum and amplitude layers, several indices) and some added, so the two sets overlap but do not match layer for layer. Check the full list and the decoding rule of every layer before comparing versions. *(ATBD 6 and Appendix A)* |
| **A full technical document** | Notes inside the code, following the published MapBiomas method. No separate technical document comes with the code we hold. | A full ATBD (Algorithm Theoretical Basis Document: the written account of every step, the reasons for it, and the measurements behind it). | The product can be checked, questioned and reproduced from the document. *(the ATBD, whole)* |
| **What deliberately did not change** | The reference colours used for the vegetation, soil and shade split. | The same values, kept by a recorded decision. | The share layers stay comparable with other countries' MapBiomas-family products. *(ATBD 5.9)* |

