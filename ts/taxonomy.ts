// Attribute taxonomy (spec §5). Each axis is scored only against its
// category's candidates. `sleeve`/`length` come from pose geometry, not CLIP.

export const TAXONOMY = {
  top: {
    type: ['t-shirt', 'polo', 'shirt', 'hoodie', 'sweater', 'tank_top', 'jersey', 'sweatshirt'],
    neckline: ['round_neck', 'v_neck', 'collared', 'crew_neck', 'turtleneck', 'hooded'],
    sleeve: ['sleeveless', 'short', 'three_quarter', 'long'],
    pattern: ['solid', 'striped', 'graphic', 'plaid', 'floral', 'colorblock'],
  },
  bottom: {
    type: ['jeans', 'joggers', 'chinos', 'trousers', 'shorts', 'cargo_pants', 'leggings', 'skirt'],
    length: ['shorts', 'cropped', 'full_length'],
    fit: ['skinny', 'slim', 'regular', 'relaxed', 'wide'],
    pattern: ['solid', 'striped', 'plaid', 'printed'],
  },
  outerwear: {
    type: ['jacket', 'denim_jacket', 'bomber', 'blazer', 'coat', 'puffer', 'cardigan', 'windbreaker'],
    pattern: ['solid', 'striped', 'plaid', 'printed'],
  },
  shoes: {
    // Deliberately coarse — shoe pixels are tiny in full-body selfies (spec §7)
    type: ['sneakers', 'boots', 'sandals', 'formal_shoes', 'loafers'],
  },
  dress: {
    type: ['dress', 'jumpsuit', 'abaya', 'kaftan'],
    length: ['mini', 'midi', 'maxi'],
    sleeve: ['sleeveless', 'short', 'long'],
  },
} as const;

export const FORMALITY_BASE: Record<string, 'formal' | 'smart_casual' | 'casual' | 'sport'> = {
  't-shirt': 'casual', 'tank_top': 'casual', 'jersey': 'sport',
  'polo': 'smart_casual', 'shirt': 'smart_casual', 'sweater': 'smart_casual',
  'hoodie': 'casual', 'blazer': 'formal', 'suit_jacket': 'formal',
  'jeans': 'casual', 'joggers': 'casual', 'shorts': 'casual',
  'chinos': 'smart_casual', 'trousers': 'formal',
  'sneakers': 'casual', 'boots': 'smart_casual', 'sandals': 'casual',
  'derby': 'formal', 'loafers': 'smart_casual',
};

// Downgrade one level (formal > smart_casual > casual > sport):
//   pattern === 'graphic'; pattern === 'plaid' (unless type is 'shirt'); distressed.
const LEVELS = ['formal', 'smart_casual', 'casual', 'sport'] as const;
export function applyFormalityModifiers(
  base: (typeof LEVELS)[number],
  opts: { pattern?: string; type?: string; distressed?: boolean },
): (typeof LEVELS)[number] {
  let i = LEVELS.indexOf(base);
  if (opts.pattern === 'graphic') i++;
  if (opts.pattern === 'plaid' && opts.type !== 'shirt') i++;
  if (opts.distressed) i++;
  return LEVELS[Math.min(i, LEVELS.length - 1)];
}
