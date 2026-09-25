# PXD2 Pinpoint

Public hall: https://pxd2.github.io/ai/

A sentence goes in. A Mayan path comes out. The same sentence comes back.
The book is the model. There is no weight file in this folder.

Our code is [MIT](LICENSE) or [Apache-2.0](LICENSE-APACHE), your choice.
The 4,500-sentence book is Princeton WordNet 3.1. See [NOTICE](NOTICE) and [book/WORDNET.txt](book/WORDNET.txt). It is not relicensed.

## Hall

Touch, voice, and keys on one screen, in the original-Xbox blade scroll with a Kodi-style underlay and overlay.

- Swipe left or right, or use the arrow keys, to move blades.
- Enter resolves Speak, or recalls a path.
- M, or Voice, uses the browser mic. Say the sentence, `recall 0.0.1`, or `pinpoint` / `field` / `core`.
- A sentence the book already knows never leaves the machine.
- A sentence it does not know is shelved in this browser. The path is never empty.

## Book

| File | What it is |
| --- | --- |
| `book/book4500.json` | 4,500 entries. `id`, `gloss`, `phrases`. |
| `book/sentences.tsv` | Same book. Columns `id`, `gloss`, `phrases` joined by `\|`. |

id 1 is `0.0.1`. id 4500 is `11.5.0`. An empty line is `0.0.0`.

## Command line

```bash
python3 pinpoint.py pin
python3 pinpoint.py say "hapless miserable pathetic."
python3 pinpoint.py recall 0.0.1
```

`say` prints the path, the balanced-ternary trench, and the sentence.
