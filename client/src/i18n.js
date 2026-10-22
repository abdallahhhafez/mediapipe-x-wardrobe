export const STRINGS = {
  appName: { en: 'Wardrobe', ar: 'خزانتي' },
  tabs: {
    ingest: { en: 'Add outfit', ar: 'إضافة إطلالة' },
    closet: { en: 'Closet', ar: 'الخزانة' },
  },
  upload: {
    title: { en: 'Add an outfit from a mirror selfie', ar: 'أضف إطلالة من صورة المرآة' },
    sub: {
      en: 'Upload a full-body photo. We detect each garment, cut it out, and check if it is already in your closet.',
      ar: 'ارفع صورة لكامل الجسم. سنتعرف على كل قطعة، ونقصّها، ونتحقق إن كانت موجودة بالفعل في خزانتك.',
    },
    pick: { en: 'Choose a photo', ar: 'اختر صورة' },
    drop: { en: 'or drag & drop it here', ar: 'أو اسحبها وأفلتها هنا' },
    privacy: { en: 'Photos are analyzed locally and never uploaded to any cloud.', ar: 'يتم تحليل الصور محليًا ولا تُرفع أبدًا إلى أي سحابة.' },
  },
  stages: {
    finding: { en: 'Finding your outfit', ar: 'نبحث عن إطلالتك' },
    identifying: { en: 'Identifying items', ar: 'نتعرف على القطع' },
    checking: { en: 'Checking your closet', ar: 'نتحقق من خزانتك' },
  },
  errors: {
    no_person: { en: "We couldn't find a person in the photo. Use a full-body photo.", ar: 'لم نجد شخصًا في الصورة. استخدم صورة لكامل الجسم.' },
    too_blurry: { en: 'The photo is too blurry — try steadier hands or more light.', ar: 'الصورة مهزوزة — جرّب بثبات أكثر أو إضاءة أفضل.' },
    too_small: { en: 'The photo resolution is too low.', ar: 'دقة الصورة منخفضة جدًا.' },
    stand_closer: { en: 'You look far away — stand closer to the mirror.', ar: 'تبدو بعيدًا — اقترب من المرآة أكثر.' },
    no_garments: { en: 'No garments detected in this photo.', ar: 'لم نتعرف على أي قطع ملابس في هذه الصورة.' },
    pipeline_failed: { en: 'Something went wrong while analyzing the photo.', ar: 'حدث خطأ أثناء تحليل الصورة.' },
  },
  review: {
    title: { en: 'Review detected items', ar: 'راجع القطع المكتشفة' },
    notFullBody: { en: 'This looks like a partial shot — a full-body photo works best.', ar: 'يبدو أن الصورة جزئية — صورة كاملة الجسم تعطي نتائج أفضل.' },
    multiPerson: { en: 'Detected more than one person — using the centered one.', ar: 'اكتشفنا أكثر من شخص — سنستخدم الشخص في المنتصف.' },
    hidden: { en: 'Partially hidden — you may want to retake.', ar: 'جزء من القطعة مخفي — قد ترغب في إعادة التصوير.' },
    unreliable: { en: "Couldn't separate this piece cleanly — check the cutout before adding.", ar: 'لم نتمكن من فصل هذه القطعة بدقة — تحقق من الصورة قبل الإضافة.' },
    matched: { en: 'Already in your closet — log a wear?', ar: 'موجودة بالفعل في خزانتك — تسجيل ارتداء؟' },
    logWear: { en: 'Log a wear', ar: 'سجّل ارتداء' },
    differentItem: { en: 'No, different item', ar: 'لا، قطعة مختلفة' },
    name: { en: 'Name', ar: 'الاسم' },
    type: { en: 'Type', ar: 'النوع' },
    color: { en: 'Color', ar: 'اللون' },
    formality: { en: 'Formality', ar: 'الطابع' },
    include: { en: 'Include', ar: 'إضافة' },
    cta: { en: (n, m) => `Add ${n} item${n === 1 ? '' : 's'} · Log ${m} wear${m === 1 ? '' : 's'}`, ar: (n, m) => `إضافة ${n} قطعة · تسجيل ${m} ارتداء` },
    nothing: { en: 'Nothing selected', ar: 'لم يتم اختيار شيء' },
    committed: { en: 'Saved to your closet', ar: 'تم الحفظ في خزانتك' },
  },
  closet: {
    title: { en: 'Your closet', ar: 'خزانتك' },
    items: { en: n => `${n} item${n === 1 ? '' : 's'}`, ar: n => `${n} قطعة` },
    empty: { en: 'Your closet is empty. Add your first outfit from a mirror selfie.', ar: 'خزانتك فارغة. أضف أول إطلالة من صورة المرآة.' },
    worn: { en: n => `worn ${n}×`, ar: n => `ارتُديت ${n}×` },
    selfie: { en: 'selfie', ar: 'سيلفي' },
  },
  categories: {
    top: { en: 'Top', ar: 'قطعة علوية' },
    bottom: { en: 'Bottoms', ar: 'بنطلون' },
    outerwear: { en: 'Outerwear', ar: 'جاكيت' },
    shoes: { en: 'Shoes', ar: 'حذاء' },
    dress: { en: 'Dress', ar: 'فستان' },
    accessory: { en: 'Accessory', ar: 'إكسسوار' },
  },
  formality: {
    formal: { en: 'Formal', ar: 'رسمي' },
    smart_casual: { en: 'Smart casual', ar: 'أنيق' },
    casual: { en: 'Casual', ar: 'كاجوال' },
    sport: { en: 'Sport', ar: 'رياضي' },
  },
};

export const TYPES = {
  top: ['t-shirt', 'polo', 'shirt', 'hoodie', 'sweater', 'tank_top', 'jersey', 'sweatshirt'],
  bottom: ['jeans', 'joggers', 'chinos', 'trousers', 'shorts', 'cargo_pants', 'leggings', 'skirt'],
  outerwear: ['jacket', 'denim_jacket', 'bomber', 'blazer', 'coat', 'puffer', 'cardigan', 'windbreaker'],
  shoes: ['sneakers', 'boots', 'sandals', 'formal_shoes', 'loafers'],
  dress: ['dress', 'jumpsuit', 'abaya', 'kaftan'],
  accessory: ['hat', 'sunglasses', 'bag', 'scarf'],
};

export function t(node, lang, ...args) {
  const v = node?.[lang] ?? node?.en ?? '';
  return typeof v === 'function' ? v(...args) : v;
}
