# How to run this

Two people need this file, and they need different halves of it.

- **Trying it out.** You want to check that the pipeline works. You build
  one small piece of the country, for one year, into a folder of your
  own. It costs little and affects nobody. That is **Part A**.
- **Building the product.** You are running the real thing: the whole of
  India, every year, into the published collection. That is **Part B**.

Do Part A first, even if you are here for Part B. It takes twenty
minutes and it proves your set-up works before you commit days of
computing to it.

A word on what is being built. A **mosaic** is one finished satellite
image of one part of India for one year, made by combining every usable
Landsat picture taken that year. India is cut into 283 rectangles called
**grid cells**, each about 111 by 150 km. One mosaic is built for each
cell and each year. The years run 1 April to 31 March, following the
crop calendar, so the year labelled 2019 means April 2019 to March 2020.

---

# Part A — try it out

## Step 1. Get the things you need

You need three.

**An Earth Engine account.** Earth Engine is Google's service for
processing satellite imagery. The building happens on Google's
computers, not yours. If you do not have an account, sign up at
earthengine.google.com and wait for approval before going further.

**A Google Cloud project** that your Earth Engine account can use. It
looks like a short name, for example `my-ee-project`. If you do not know
yours, it is shown at the top of the Earth Engine Code Editor.

**Python, and two packages.** Anything from Python 3.9 onwards is fine.

## Step 2. Copy the code onto your computer

In a terminal:

```
git clone --branch india-v2 https://github.com/openlandcover/countries-mosaics.git
cd countries-mosaics/india
pip install -r requirements.txt
```

That last command installs the Earth Engine library and Jupyter, which
is what opens the notebook.

## Step 3. Let Earth Engine know it is you

Once, in the same terminal:

```
earthengine authenticate
```

A browser window opens. Sign in with the Google account your Earth
Engine access belongs to. When it says you are authenticated, close it.

## Step 4. Open the notebook

```
jupyter notebook notebooks/run_mosaics.ipynb
```

A page opens in your browser showing the notebook: a column of boxes,
some of them explanation, some of them code. You run a box by clicking
it and pressing Shift and Enter together.

## Step 5. Fill in four things

The first code box is the only one you edit. Change these:

- `MODE` — leave it as `'development'`.
- `EE_PROJECT` — put your cloud project name in the quotes.
- `DEV_COLLECTION` — where your mosaic will be written. Use a path
  inside your own project, for example
  `'projects/my-ee-project/assets/mosaic_trial'`. It does not have to
  exist; it is created for you.
- `CELL` and `YEARS` — leave them. They point at a test cell in the
  Western Ghats for 2019.

Leave everything else alone.

## Step 6. Run it, in order

Run the boxes from the top, one at a time.

The **setup box** prints what you are about to do and where it will go.
Read those lines. If they do not say what you expect, stop and fix the
first box rather than carrying on.

The **development box** queues the work. It prints one line saying a
task has been queued. That is the whole job: you have handed the work to
Google.

The **tracking box** tells you how it is going. Run it whenever you
like. At first it will say nothing has finished. A mosaic takes a while,
often an hour or more.

You can now close the notebook. The work carries on without it. Come
back later, open the notebook, run the setup box and then the tracking
box, and it will tell you where things stand.

**You are done when** the tracking box says every planned mosaic is
present. Your mosaic is sitting in the folder you named, and you can
open it in the Earth Engine Code Editor.

---

# Part B — build the product

Everything in Part A applies. The differences are below.

**Before you start, you need write access to the published collection.**
That is a permission somebody grants you; it is not something this code
can arrange. Without it nothing will work, and Step 3 below will tell
you so before any harm is done.

This is a big job: 283 cells times 40 years, so **11,320 pieces of
work**. It takes days. It is meant to be done in several sittings, and
stopping partway costs you nothing.

## Step 1. Set the mode

In the first code box:

- `MODE` — change it to `'production'`.
- `EE_PROJECT` — your cloud project, as before.
- `CONFIRM` — leave it empty for now.
- Leave `MAX_TASKS` as `None`.

You do not need to touch `DEV_COLLECTION`. Production mode ignores it
and writes to the published collection.

## Step 2. Run the setup box

It prints where the work is going, and then one line that matters more
than the rest:

```
destination reachable: yes
```

If it says **no**, stop. You do not have write access yet. Sort that out
first. Nothing else in this file will work until that line says yes.

## Step 3. Look before you leap

Run the **plan box**. It queues nothing at all. It prints how many
pieces of work there are and where they would go. Read it. This is your
last quiet moment.

## Step 4. Say the words

Go back to the first box and set:

```
CONFIRM = 'QUEUE THE NATIONAL RUN'
```

It must match exactly. This is deliberate. It is the only thing standing
between a stray keypress and eleven thousand jobs.

Run the first box again so the change takes effect, then run the
**queueing box**.

### Setting up the collection itself

The first time you run the queueing box, it does two things before it
queues anything.

It **creates the collection**, if it is not already there. A collection
is the folder inside Earth Engine that the 11,320 mosaics will sit in.

It **writes the collection's description**: a page of plain text saying
what the product is, how to decode every layer, what to watch out for,
and who to credit. Anyone who finds the collection later reads that and
knows what they are looking at. Nothing else ever writes it, which is
why it is done here, once, at the very start rather than at the end.

The words come from `docs/collection_description.txt` in this
repository. If you want to read them before they go on, open that file.

If for any reason the description cannot be written, **the run carries
on regardless**. Building the product matters more than labelling it.
You will see a line saying it could not be written, and you can put it
on afterwards, at any time, with:

```
python scripts/set_collection_description.py --set
```

That command shows you the text and writes nothing unless you add
`--set`. Running it twice does nothing the second time. Only the owner
of the collection can run it, which is whoever ran the export.

## Step 5. Let it fill up, then come back

Earth Engine will only hold so many waiting jobs at once. How many
depends on your account, and **you do not need to know the number**.
When it will take no more, the run stops by itself and tells you how
many it queued and how far it reached. That is normal and expected. It
is not an error.

So: run the queueing box, let the jobs drain over some hours, run it
again. Repeat until it says everything is queued.

**Running it again never repeats work.** A piece that is already built,
or already being built, is skipped.

## Step 6. Watch it to the end

Run the **tracking box** whenever you want. It reads the true state from
Earth Engine, so it works after you close the notebook, and it works
from a different computer than the one you started on.

It tells you how many are finished, how many are being worked on now,
how many are waiting, how many have not started, and how many failed.

You are finished when it says every planned mosaic is present.

---

# When something goes wrong

**A few pieces failed.** Normal in a job this size. Run the queueing box
again; failures are simply retried, because a failed piece was never
built.

**The run stopped and said many failed one after another.** It stopped
on purpose. When a long line of pieces fail in a row, the fault is
almost never the pieces: it is the set-up. Usually it is missing write
access, or your sign-in has expired. Fix that, then start again. Nothing
already queued is lost.

**The tracking box says it cannot report progress.** It cannot read the
destination. Same cause as above.

**You closed the notebook, or your computer restarted.** Nothing is
lost. The work is on Google's computers. Open the notebook, run the
setup box, then the tracking box.

**You want to do this from a terminal instead**, which is steadier for
something taking days:

```
python -m pipeline.run_production --plan
python -m pipeline.run_production --run --confirm "QUEUE THE NATIONAL RUN"
python -m pipeline.run_production --progress
```

---

# What to read next

`docs/README.md` says what every document in this repository is.

The full account of the product, how it is built and what its limits
are, is `docs/IOLN Landsat Mosaics ATBD.pdf`.
