/** Browser-side reader for the `<0f>` object prompt the backend seeds. */

export type SamBox = { id: number; x1: number; y1: number; x2: number; y2: number };

const BOX = /<obj id="(\d+)"><box x1="([0-9.]+)" y1="([0-9.]+)" x2="([0-9.]+)" y2="([0-9.]+)"\s*\/><\/obj>/g;

export function parseObjectPrompt(prompt: string): SamBox[] {
  const boxes: SamBox[] = [];
  for (const match of prompt.matchAll(BOX)) {
    boxes.push({
      id: Number(match[1]),
      x1: Number(match[2]),
      y1: Number(match[3]),
      x2: Number(match[4]),
      y2: Number(match[5]),
    });
  }
  return boxes;
}
