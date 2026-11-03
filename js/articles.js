/*==================== BLOG CONTENT ====================*/
/* Single source of truth for the blog. Edit by hand, or generate this file with
   write.html (local-only writer) and commit the result. */

const BLOG_ARTICLES = [
    {
        slug: "swahili-asr-baseline",
        title: "Building a Swahili ASR Baseline From Scratch",
        excerpt: "The shortest path to a usable Swahili speech-to-text model, and the data decisions that decide the outcome before training starts.",
        date: "2026-10-14",
        readTime: "8 min read",
        tags: ["ASR", "Swahili", "Training"],
        image: "img/blog1.jpg",
        imageAlt: "TODO: replace with a real figure for this article",
        body: [
            "<p><strong>TODO:</strong> opening paragraph. State the problem this article solves and what a reader can expect to reproduce.</p>",

            "<h3>Why a baseline first</h3>",
            "<p><strong>TODO:</strong> explain why you measure a naive baseline before touching a pretrained checkpoint.</p>",

            "<h3>Data</h3>",
            "<ul><li>TODO: corpus source, hours, sampling rate, dialect mix.</li><li>TODO: cleaning and normalisation steps.</li><li>TODO: train/validation/test split policy.</li></ul>",

            "<h3>Training</h3>",
            "<p><strong>TODO:</strong> model choice, fine-tuning strategy, hyperparameters.</p>",
            "<pre><code>TODO: paste the command or config that actually reproduced this run</code></pre>",

            "<h3>Results</h3>",
            "<p><strong>TODO:</strong> real numbers only. Do not publish a WER or CER figure here that you cannot trace back to an eval script.</p>",

            "<h3>Takeaways</h3>",
            "<ul><li>TODO</li><li>TODO</li></ul>"
        ].join("\n")
    },

    {
        slug: "low-resource-tts",
        title: "Flow-Matching TTS for Low-Resource Languages",
        excerpt: "What changes when you move from a two-speaker demo voice to a multilingual synthesiser that has to survive production traffic.",
        date: "2026-09-22",
        readTime: "10 min read",
        tags: ["TTS", "Speech synthesis", "PyTorch"],
        image: "img/blog2.jpg",
        imageAlt: "TODO: replace with a real figure for this article",
        body: [
            "<p><strong>TODO:</strong> opening paragraph. Name the gap between a demo voice and a shippable multilingual voice.</p>",

            "<h3>The text front-end is the product</h3>",
            "<ul><li>TODO: normalisation rules you had to write.</li><li>TODO: phonemisation and prosody decisions for the languages covered.</li></ul>",

            "<h3>Acoustic model and vocoder</h3>",
            "<p><strong>TODO:</strong> architecture, conditioning signals, training data volume.</p>",
            "<pre><code>TODO: paste the training snippet or model config</code></pre>",

            "<h3>Serving</h3>",
            "<p><strong>TODO:</strong> latency budget, batching, streaming, GPU queue design.</p>",

            "<h3>Listening tests</h3>",
            "<p><strong>TODO:</strong> how you evaluated naturalness, and with whose ears. Include audio examples here.</p>",

            "<h3>Takeaways</h3>",
            "<ul><li>TODO</li><li>TODO</li></ul>"
        ].join("\n")
    },

    {
        slug: "consented-speech-datasets",
        title: "Curating Consented Speech Data in Kenya",
        excerpt: "The unglamorous work behind every usable African speech model: consent, provenance, labelling quality and versioning.",
        date: "2026-08-30",
        readTime: "7 min read",
        tags: ["Datasets", "Labelling", "Ethics"],
        image: "img/blog3.jpg",
        imageAlt: "TODO: replace with a real figure for this article",
        body: [
            "<p><strong>TODO:</strong> opening paragraph. Frame consent and provenance as engineering constraints, not paperwork.</p>",

            "<h3>Recording operations</h3>",
            "<ul><li>TODO: capture setup, device mix, environments.</li><li>TODO: how consent is captured and stored alongside the audio.</li></ul>",

            "<h3>Labelling workflow</h3>",
            "<p><strong>TODO:</strong> task schema, annotator training, reviewer rounds, gold sets.</p>",

            "<h3>Measuring label quality</h3>",
            "<p><strong>TODO:</strong> inter-annotator agreement metric and the thresholds you act on.</p>",

            "<h3>Versioning a corpus</h3>",
            "<p><strong>TODO:</strong> content hashing, release notes, what a retrain can rely on.</p>",

            "<h3>What I would do differently</h3>",
            "<ul><li>TODO</li><li>TODO</li></ul>"
        ].join("\n")
    }
];

/*==================== CONTENT SOURCE ====================*/
/* Set BLOG_CMS_ENABLED to true and implement fetchRemoteArticles() to serve live
   content from Supabase, Airtable or any JSON endpoint instead of the array above.
   Everything else in the blog reads through loadArticles() and stays unchanged. */

const BLOG_CMS_ENABLED = false;

async function fetchRemoteArticles() {
    // TODO: replace with the real call once credentials exist, e.g.
    //   const res = await fetch(`${BLOG_CMS_URL}/articles?_fields=slug,title,...`, {headers: {...}})
    //   return (await res.json()).map(normaliseCmsRow)
    throw new Error("No CMS configured. Set BLOG_CMS_ENABLED to false, or implement fetchRemoteArticles().");
}

async function loadArticles() {
    if (BLOG_CMS_ENABLED) return fetchRemoteArticles();
    return [...BLOG_ARTICLES].sort((a, b) => b.date.localeCompare(a.date));
}
