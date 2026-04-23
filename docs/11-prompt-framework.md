# 11 — Multi-stage prompt framework

SD.Next's pipeline exposes up to **three distinct inference passes** per
image — base, hires refine, and detailer — each accepting its own prompt
and negative. The default "flat prompt" approach wastes this separation by
jamming everything into the main prompt. This doc documents a **six-block
architecture** that treats each pass deliberately.

Validated against **demanding composite prompts** — the class of SDXL work
where multiple focus areas (character / costume / props / anatomy / scene)
need to coexist coherently without one dominating or merging into another.
Pipelines that work here tend to work on easier tasks. Those that work on
easy tasks often collapse here.

## Why flat prompts fail on demanding compositions

A single prompt string across Base + Hires + Detailer means:

- **Base** is asked to solve composition AND detail at once → spends token
  budget on fine details that will be regenerated in Hires anyway
- **Hires img2img at strength 0.99** nearly repaints everything → base's
  careful composition gets over-written
- **Detailer** receives the whole scene prompt but only operates on a cropped
  face region → wastes conditioning on body / costume / environment tokens
  the YOLO crop doesn't contain

The fix is to give each pass a **purpose-built prompt** matching what it
actually does.

## The six blocks

```
Base pass       →  mpp (Main Positive Prompt) + mnp (Main Negative Prompt)
Hires refine    →  rpp (Refine Positive Prompt) + rnp (Refine Negative Prompt)
Detailer        →  dpp (Detailer Positive Prompt) + dnp (Detailer Negative Prompt)
```

### Block purposes

| Block | Scope | Format |
|---|---|---|
| **mpp** | Overall composition, main subject, primary pose, core anatomy anchors | Can use multiple `BREAK` segments for sub-topics |
| **mnp** | Universal quality + anatomy negatives (bad_hands, deformed, extra_limbs, worst_quality, etc.) | Single segment, no `BREAK` |
| **rpp** | Detail refinement — specific anatomy / costume / small props / ornaments. What the hires pass should sharpen and reinforce | Multiple `BREAK` segments: one per focus area |
| **rnp** | Detail-phase negatives specific to the refined elements (over_smoothed, plastic_skin, wrong_costume_type, etc.) | Single segment |
| **dpp** | Face-specific — facial features, expression, eye detail, skin quality, hair around face | Single segment, focused |
| **dnp** | Face-specific negatives (asymmetric_eyes, plastic_skin, blemishes, etc.) | Single segment |

### Why this ordering matters

1. **Base (mpp)** locks the **composition** — limb positions, subject scale,
   perspective, scene. Don't waste tokens on things the later passes will
   redo.

2. **Hires (rpp)** is img2img at strength 0.75-0.99 — it takes the upscaled
   base image and repaints it. This is where **"give it the detail-level
   tokens"** pays off: the model now has the resolution headroom to render
   what those tokens describe.

3. **Detailer (dpp)** gets a 1024×1024 crop of just the face. Anything in
   `dpp` that isn't about the face is token waste. Purely facial vocabulary
   lets the detailer pour all its CFG budget into the face.

## Formatting rules (strict)

### Rule 1 — No spaces after commas

**Correct:**
```
realistic,photorealistic,sharp_focus
```

**Wrong:**
```
realistic, photorealistic, sharp_focus
```

SDXL tokenizers treat `realistic,` and ` realistic` differently — the space
creates a different token sequence. Commas without space maximize token
efficiency and keep weights cleanly attached.

### Rule 2 — `BREAK` with zero whitespace

**Correct:**
```
hands_firmly_on_hipsBREAK
main_subject_anchors,...
```

**Wrong:**
```
hands_firmly_on_hips BREAK
hands_firmly_on_hips<newline>BREAK
hands_firmly_on_hips , BREAK
```

`BREAK` is a magic token that starts a new conditioning segment. Any
whitespace around it dilutes that effect. Some parsers tolerate it; A1111
parser (which this repo uses) is strict about adjacency.

### Rule 3 — Block ordering: broad-to-narrow, critical-first

Recommended sequence within each positive block:

```
quality tokens → main subject → pose / composition → clothing → environment → focus ornaments
```

Rationale: SDXL's attention gives disproportionate weight to **early tokens**.
Put the things that must not be dropped first. Put decorative details last.

### Rule 4 — Use underscores, not spaces, for compound concepts

**Correct:** `sharp_focus`, `razor_thin_legs`, `v_shaped_jawline`

**Wrong:** `sharp focus`, `razor thin legs`

Underscores create a single token that the model treats as a learned concept.
Spaces split it into multiple independent tokens — the model may attend to
each separately and lose the compositional meaning.

## Example skeleton

Note: this is a **template**, not a literal prompt. Swap your own subject /
style / pose tokens in. The structure is what matters.

### mpp (Main Positive)
```
quality_tokens,BREAK
main_subject_type,primary_pose,composition_anchors,BREAK
body_silhouette_tokens,BREAK
environment_context,depth_of_field
```

### mnp (Main Negative)
```
bad_anatomy,deformed,extra_limbs,worst_quality,low_quality,blurry,ugly,lowres,
censored,jpeg_artifacts,grainy,overexposed,underexposed,glitch
```

### rpp (Refine Positive)
```
body_focus,detailed_anatomy_tokens,proportions_tokens,BREAK
costume_focus,material_tokens,fabric_details,color_tokens,BREAK
prop_focus,object_specific_detail_tokens,BREAK
footwear_focus,shoe_type,heel_geometry,foot_pose,BREAK
environment_focus,quality_tokens,ambient_tokens
```

### rnp (Refine Negative)
```
over_smoothed,plastic_skin,waxy_skin,bad_detail,artifact,noise,grain,
overexposed,underexposed,jpeg_artifacts,glitch,
costume_mistakes_specific_to_your_subject
```

### dpp (Detailer Positive)
```
score_9,specific_face_reference,facial_feature_tokens,expression_tokens,
eye_detail_tokens,hair_around_face_tokens
```

### dnp (Detailer Negative)
```
over_smoothed,plastic_skin,deformed_eyes,asymmetric_eyes,moles,beauty_mark,
skin_spots,freckles,facial_blemish,blurry_face,noise,grain,artifacts
```

## Common failure modes this structure prevents

| Symptom | Root cause | Fix |
|---|---|---|
| Prop or costume element appears in wrong place (limb, face, background) | Detail token in `mpp` gets diffused across whole composition | Move to `rpp` with appropriate focus anchor |
| Face looks different from body skin tone | Detailer generating face from scratch without facial prompt anchors | Strengthen `dpp`, ensure `Refiner start: 0.5` so detailer partial-denoises |
| Body proportions drift in hires | `rpp` missing the proportion tokens | Add proportion / pose tokens to `rpp` main-subject block |
| Over-smoothed / plastic skin | Negative lacks texture negatives | Ensure `rnp` has `over_smoothed,plastic_skin,waxy_skin,greasy_skin` |
| Prompt order in token budget matters | Critical tokens placed late got dropped | Reorder using "broad-to-narrow" rule |

## Relationship to `Refiner start`

The `Refiner start` UI slider controls **detailer's** `denoising_start`:
- `0.5` = detailer partial-denoises from 50% noise (preserves face anchors)
- `0` or `1` = detailer full-repaints from pure noise (face disconnects from body)

Keep it at `0.5`. The dpp / dnp blocks are designed around this behavior —
they're guiding a refinement, not dictating a regeneration.

See [07-troubleshooting.md](07-troubleshooting.md) for the red-face / wrong-size
face failure mode if this gets misconfigured.

---

## Summary

```
Flat prompt:                 One string → three passes → attention diluted
Six-block architecture:      Six strings → three purpose-matched passes → every token earns its place
```

If you're routinely hitting the wall where demanding composite prompts
produce incoherent or body-horror results, this structure is almost always
the missing layer — not more LoRAs, not more steps, not a different sampler.
