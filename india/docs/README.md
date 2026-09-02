# What is in this folder

Two kinds of thing live here.

The **two documents** describe the product: what it is, how it is built,
and how it compares with the version that came before. Read those first,
and you may not need anything else.

The **working records** are the notes behind those documents: the
decisions, the measurements that settled them, and the contracts the
code has to keep. They exist so that a claim in the ATBD can be traced
to the day it was decided and the numbers that decided it. They are not
a second, fuller account of the product. The ATBD is the account; these
are its workings.

---

## Start here

- **[IOLN Landsat Mosaics ATBD.pdf](IOLN%20Landsat%20Mosaics%20ATBD.pdf)**
  The full method record, 154 pages. What the product is, every step of
  how it is made, what was measured, what its limits are, and how to
  decode every band. Written for a reader with no background in
  satellites. If you read one thing, read this.

- **[IOLN Landsat Mosaics V1-vs-V2.pdf](IOLN%20Landsat%20Mosaics%20V1-vs-V2.pdf)**
  Two pages, side by side: what version 1 did, what version 2 does, and
  what each change gains. Every claim in it about version 1 was checked
  against the older product's own code and published data. Read this if
  you already know version 1 and want to know what moved.

## Why the pipeline is the way it is

Decisions, with the reasoning kept.

- **design_decisions.md** — the condensed record of every design choice,
  and why it went the way it did. The quickest route into the thinking.
- **band_value_ranges.md** — which layers to keep and which to drop.
  Three reviewers answered the same eight questions independently; this
  is where that landed.
- **terrain_correction_evidence.md** — how hillside lighting is removed,
  and why that method was chosen over the alternatives that were tried.
- **collection_description.md** — what the published collection's own
  description should say, and in what order.
- **collection_description.txt** — that description, as the plain text
  set on the collection. See "Publishing" below.

## What was actually measured

The evidence behind particular claims. Each was a piece of work with a
question, a method and a result.

- **cloud_masking_evidence.md** — how much cloud each masking method
  lets through, measured rather than assumed.
- **evidence_checks.md** — the smaller checks, gathered as each landed.
- **evidence_endmembers.md** — where the reference colours used for
  splitting a pixel into ground types come from, and what is known and
  not known about them.
- **evidence_sensor_harmonisation.md** — how the transform that puts the
  older satellite onto the newer one's basis was derived.

## What the code must satisfy

Contracts. Change these and the product version has to change with them.

- **band_and_property_contract.md** — every band and every image
  property the product promises to carry.
- **input_assets_and_run_order.md** — which inputs the build reads, and
  the order things must happen in.

## Looking at the data

Paste either into the Earth Engine Code Editor.

- **viewer_year_slider.js** — step through the years for one place.
- **viewer_v1_v2_compare.js** — the two versions side by side.

---

## Publishing

The collection carries one plain-text description saying what it is and
how to read it. Nothing in the export writes it, so it is set once by
hand, by whoever owns the collection:

    python scripts/set_collection_description.py --set

It shows the text and writes nothing without `--set`. The words come
from `collection_description.txt`, so changing them means editing a text
file, not code.

## A note on dates and names

These records are dated and were written as the work happened, so they
sometimes name things by their older names. Where a record and the ATBD
disagree, **the ATBD is right**: it was written last and checked
against the code. Where a record mentions a file that is not in this
repository, it belongs to the project's own working archive and is not
part of this release.
