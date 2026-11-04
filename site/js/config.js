/* Where the app reads its data.
   - Local development (pipeline/scripts/serve.py on 127.0.0.1 / localhost): everything from ../data/
   - Published site (GitHub Pages): the small, often-requested files (SITE below) from the repository's own
     data/ folder (../data/), everything else from the Hugging Face dataset
   - Override for testing: ?data=hf uses the published routing (SITE files from ../data/, the rest from
     Hugging Face) on any host; ?data=local reads everything from ../data/
   Use dataUrl(path) for every data file (path relative to the data root, e.g. "meta/layers.json"). */
const HF_DATA = "https://huggingface.co/datasets/aaguilar90/mosaic-ucayali/resolve/main/";
const LOCAL_DATA = "../data/";

/* served from GitHub Pages: folder prefixes (ending in "/") or single files. GitHub refuses files over
   100 MB: keep an eye on tile sizes (pipeline 91_publish_check.py reports them) and move anything close
   to the limit off this list so it falls back to Hugging Face. */
export const SITE = ["meta/", "series/", "vectors/", "figures/", "fonts/",
                     "tiles/osm_basemap.pmtiles", "tiles/terrain.pmtiles", "tiles/s2_rgb.pmtiles"];

const choice = new URLSearchParams(location.search).get("data");
const isLocal = ["127.0.0.1", "localhost"].includes(location.hostname);
const allLocal = choice === "local" || (choice !== "hf" && isLocal);

const onSite = (path) => SITE.some((s) => (s.endsWith("/") ? path.startsWith(s) : path === s));

export const dataUrl = (path) => (allLocal || onSite(path) ? LOCAL_DATA : HF_DATA) + path;

/* never published: with the published routing the app treats these as absent without requesting them,
   so the public site logs no 404s; locally they are probed as usual. (Empty for now - RAISG Indigenous
   territories would go here if a local display copy is ever prepared; decision D6 keeps them out.) */
const WITHHELD = [];
export const isWithheld = (path) => !allLocal && WITHHELD.includes(path);
