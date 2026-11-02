// Small BM25 index for the offline search box: the same scoring as the Python index,
// without embeddings, so it runs in the browser with no API key.
const STOP = new Set(
  "a an and are as at be but by can could did do does for from had has have he her his how i if in into is it its me my no not of on or our she so that the their them then there these they this to us was we were what when where which who why will with would you your".split(" "),
);

export const tokens = (text: string) =>
  (text.toLowerCase().replace(/’/g, "'").match(/[a-z0-9$%]+(?:'[a-z]+)?/g) ?? []).filter((t) => !STOP.has(t));

export class BM25<T> {
  private docs: Map<string, number>[];
  private lengths: number[];
  private avg: number;
  private idf = new Map<string, number>();

  constructor(private items: T[], text: (item: T) => string, private k1 = 1.5, private b = 0.75) {
    this.docs = items.map((it) => {
      const m = new Map<string, number>();
      for (const t of tokens(text(it))) m.set(t, (m.get(t) ?? 0) + 1);
      return m;
    });
    this.lengths = this.docs.map((d) => [...d.values()].reduce((a, c) => a + c, 0));
    this.avg = this.lengths.reduce((a, c) => a + c, 0) / Math.max(1, this.lengths.length);
    const df = new Map<string, number>();
    for (const d of this.docs) for (const t of d.keys()) df.set(t, (df.get(t) ?? 0) + 1);
    const n = this.docs.length;
    for (const [t, f] of df) this.idf.set(t, Math.log(1 + (n - f + 0.5) / (f + 0.5)));
  }

  search(query: string, k = 6): { item: T; score: number }[] {
    const q = tokens(query);
    return this.docs
      .map((d, i) => {
        let s = 0;
        for (const t of q) {
          const f = d.get(t);
          if (f) s += (this.idf.get(t) ?? 0) * ((f * (this.k1 + 1)) / (f + this.k1 * (1 - this.b + (this.b * this.lengths[i]) / this.avg)));
        }
        return { item: this.items[i], score: s };
      })
      .filter((h) => h.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, k);
  }
}
