"""Put the human-readable description onto the published collection.

The collection asset carries one plain-text description saying what the
product is, how to decode it, and what to watch out for. Nothing in the
export writes it: an export makes images, not the folder they sit in.
So it is set once, by hand, with this script.

WHO RUNS THIS. Whoever owns the published collection. That is the person
who ran the national export, not necessarily the person who wrote the
pipeline, because only the owner of an asset may change it. If you did
not create the collection, this script will tell you plainly that you
cannot write to it.

WHEN TO RUN IT. Once, after the collection exists and the first images
are in it. Again only if the wording changes, or if the recipe version
changes.

The words live in docs/collection_description.txt, beside this script's
repository, so that changing them is an edit to a text file and not to
code. The text is not generated: it was written and cleared by hand.

    python scripts/set_collection_description.py                 # show
    python scripts/set_collection_description.py --set           # write
    python scripts/set_collection_description.py --collection ...
"""

import argparse
import io
import os
import sys

import ee

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from pipeline import config as C          # noqa: E402

TEXT_FILE = os.path.join(ROOT, 'docs', 'collection_description.txt')

# The property the Earth Engine Code Editor shows under an asset. Kept in
# one place because two names are in circulation and only this one is
# read by the asset browser.
DESCRIPTION_PROPERTY = 'description'


def read_text(path=None):
    """The description text, as written and cleared by hand."""
    path = path or TEXT_FILE
    with io.open(path, encoding='utf-8') as handle:
        text = handle.read().strip('\n')
    if not text:
        raise SystemExit('{} is empty; nothing to set.'.format(path))
    return text


def current(collection_path):
    """What the collection says about itself now, or None."""
    asset = ee.data.getAsset(collection_path)
    return asset.get('properties', {}).get(DESCRIPTION_PROPERTY)


def apply(collection_path, text):
    """Write the description. Only the owner of the asset may do this."""
    ee.data.updateAsset(collection_path,
                        {'properties': {DESCRIPTION_PROPERTY: text}},
                        ['properties.' + DESCRIPTION_PROPERTY])


def main():
    parser = argparse.ArgumentParser(
        description='Set the collection description. Shows it by default; '
                    'writes only with --set.')
    parser.add_argument('--collection', default=None,
                        help='which collection (default: the published one)')
    parser.add_argument('--text', default=None,
                        help='a different text file to read')
    parser.add_argument('--set', action='store_true',
                        help='actually write it')
    args = parser.parse_args()

    ee.Initialize(project=C.EE_PROJECT)
    collection_path = args.collection or C.PRODUCTION_COLLECTION
    text = read_text(args.text)

    print('collection: {}'.format(collection_path))
    print('text:       {} ({} characters)'
          .format(args.text or TEXT_FILE, len(text)))

    try:
        existing = current(collection_path)
    except Exception as e:
        raise SystemExit(
            '\ncannot read {}: {}\n'
            'The collection has to exist before it can be described. It is '
            'created by the export, so run the export first.'
            .format(collection_path, e))

    if existing is None:
        print('now:        no description set')
    elif existing == text:
        print('now:        already exactly this text -- nothing to do')
        return
    else:
        print('now:        a different description of {} characters is set; '
              'it would be replaced'.format(len(existing)))

    if not args.set:
        print('\n----- the text that would be written -----')
        print(text)
        print('----- end -----')
        print('\nNothing was written. Add --set to write it.')
        return

    try:
        apply(collection_path, text)
    except Exception as e:
        raise SystemExit(
            '\ncould not write to {}: {}\n'
            'Only the owner of an asset may change it. If you did not create '
            'this collection, ask whoever did to run this script.'
            .format(collection_path, e))

    written = current(collection_path)
    if written == text:
        print('\nwritten, and read back to confirm.')
    else:
        raise SystemExit('\nwrote the description but it did not read back '
                         'the same. Check the asset by hand.')


if __name__ == '__main__':
    main()
