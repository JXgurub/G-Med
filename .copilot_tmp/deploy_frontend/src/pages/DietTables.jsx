import { useMemo, useState } from 'react'
import './DietTables.css'

const dietTables = [
  {
    number: '0',
    name: 'Operatsiyadan keyingi yengil ovqatlanish',
    category: 'Ovqat hazm qilish',
    summary: 'Ayrim operatsiyalardan keyingi dastlabki davrda ovqatni bosqichma-bosqich kiritish uchun.',
    principle: 'Taomlar shifokor belgilagan bosqichga qarab suyuq, ezilgan yoki yumshoq holatda beriladi.',
    foods: ['Suyuq bo‘tqa va sho‘rvalar', 'Bug‘da pishirilgan yengil taomlar', 'Ruxsat etilgan ichimliklar'],
    limit: 'Qattiq ovqat, gazli ichimlik va og‘ir hazm bo‘ladigan taomlar — faqat davolovchi jamoa ko‘rsatmasiga ko‘ra.',
    mealIdeas: 'Yumshoq bo‘tqa, yengil sho‘rva yoki shifokor ruxsat bergan pyure.'
  },
  {
    number: '1',
    name: 'Oshqozonni asrovchi ovqatlanish',
    category: 'Ovqat hazm qilish',
    summary: 'Oshqozon yarasi yoki kislotalilik bilan bog‘liq ayrim holatlarda buyurilishi mumkin.',
    principle: 'Oshqozonni bezovta qilmaydigan, yumshoq tayyorlangan taomlar tanlanadi.',
    foods: ['Bo‘tqa va yengil sho‘rvalar', 'Bug‘da yoki qaynatib pishirilgan taomlar', 'Yumshoq pishgan sabzavotlar'],
    limit: 'Juda achchiq, qovurilgan yoki bemorda alomatlarni kuchaytiradigan taomlar.',
    mealIdeas: 'Suli bo‘tqasi, sabzavotli pyure-sho‘rva, bug‘da pishgan kotlet.'
  },
  {
    number: '2',
    name: 'Hazmni yengillashtiruvchi ovqatlanish',
    category: 'Ovqat hazm qilish',
    summary: 'Oshqozon faoliyati pasaygan ayrim holatlarda mutaxassis tavsiya qilishi mumkin.',
    principle: 'Yengil hazm bo‘ladigan taomlar va ovqatlanish tartibi individual belgilanadi.',
    foods: ['Yog‘siz go‘sht yoki baliq', 'Pishirilgan sabzavotlar', 'Yaxshi pishgan yormalar'],
    limit: 'Haddan tashqari yog‘li, qovurilgan va og‘ir hazm bo‘ladigan taomlar.',
    mealIdeas: 'Yengil sabzavotli sho‘rva, qaynatilgan baliq, guruchli bo‘tqa.'
  },
  {
    number: '3',
    name: 'Ichak faoliyatini qo‘llab-quvvatlash',
    category: 'Ovqat hazm qilish',
    summary: 'Qabziyatga moyillikda, qarshi ko‘rsatmalar bo‘lmasa, tolaga boy ovqatlanish tamoyillarini eslatadi.',
    principle: 'Suv ichish, harakat va tolali mahsulotlar miqdori shaxsiy holatga mos bo‘lishi kerak.',
    foods: ['Sabzavot va mevalar', 'Suli yoki grechka yormasi', 'Shifokor ruxsat bergan dukkaklilar'],
    limit: 'Kam suyuqlik ichish va ratsionda tolali mahsulotlarning juda kam bo‘lishi.',
    mealIdeas: 'Sabzavotli salat, suli bo‘tqasi, meva qo‘shilgan qatiq.'
  },
  {
    number: '4',
    name: 'Ichakni asrovchi ovqatlanish',
    category: 'Ovqat hazm qilish',
    summary: 'Ich ketishi bilan kechadigan ayrim ichak kasalliklarida vaqtincha buyurilishi mumkin.',
    principle: 'Suyuqlik yo‘qotilishini qoplash va ichakni bezovta qiluvchi mahsulotlarni cheklash muhim.',
    foods: ['Guruchli bo‘tqa yoki sho‘rva', 'Yog‘siz, qaynatilgan taomlar', 'Shifokor tavsiya qilgan suyuqliklar'],
    limit: 'Yog‘li, achchiq taomlar va bemorda alomatlarni kuchaytiradigan mahsulotlar.',
    mealIdeas: 'Guruchli sho‘rva, suvda pishgan bo‘tqa, qaynatilgan yog‘siz go‘sht.'
  },
  {
    number: '5',
    name: 'Jigar va o‘t yo‘llarini asrovchi ovqatlanish',
    category: 'Jigar va buyrak',
    summary: 'Jigar, o‘t pufagi yoki o‘t yo‘llarining ayrim kasalliklarida tavsiya etilishi mumkin.',
    principle: 'Qovurish o‘rniga qaynatish, dimlash yoki bug‘da pishirish tanlanadi.',
    foods: ['Sabzavot va yormalar', 'Yog‘siz go‘sht yoki baliq', 'Yengil sut mahsulotlari'],
    limit: 'Qovurilgan, juda yog‘li taomlar va shifokor cheklagan mahsulotlar.',
    mealIdeas: 'Sabzavotli sho‘rva, grechka bilan bug‘da pishgan baliq, tvorogli yengil taom.'
  },
  {
    number: '6',
    name: 'Purinni nazorat qiluvchi ovqatlanish',
    category: 'Moddalar almashinuvi',
    summary: 'Podagra yoki siydik kislotasi bilan bog‘liq ayrim holatlarda mutaxassis ko‘rsatmasi bilan.',
    principle: 'Suyuqlik va purin miqdori buyrak faoliyati hamda boshqa kasalliklarni hisobga olgan holda belgilanadi.',
    foods: ['Sabzavot va don mahsulotlari', 'Shifokor ruxsat bergan sut mahsulotlari', 'Yetarli suyuqlik — agar cheklanmagan bo‘lsa'],
    limit: 'Ichki a’zolar go‘shti va ayrim purini ko‘p mahsulotlar bo‘yicha shifokor bilan maslahat zarur.',
    mealIdeas: 'Sabzavotli dimlama, sutli bo‘tqa, yengil sabzavot sho‘rvasi.'
  },
  {
    number: '7',
    name: 'Buyrak faoliyatiga mos ovqatlanish',
    category: 'Jigar va buyrak',
    summary: 'Buyrak kasalliklarida tuz, oqsil va suyuqlik miqdori tahlillar asosida belgilanadi.',
    principle: 'Bitta umumiy menyu yo‘q: buyrak faoliyati va davolash turiga qarab cheklovlar farq qiladi.',
    foods: ['Shifokor belgilagan miqdordagi oqsil', 'Uyda tuzi nazorat qilingan taomlar', 'Tahlillarga mos sabzavot-mevalar'],
    limit: 'Tuz, suyuqlik, kaliy yoki fosforni o‘zboshimchalik bilan cheklamang — aniq miqdorni shifokor belgilaydi.',
    mealIdeas: 'Tuz miqdori va mahsulot tanlovi nefrolog yoki dietolog ko‘rsatmasi bilan.'
  },
  {
    number: '8',
    name: 'Vaznni nazorat qilish',
    category: 'Moddalar almashinuvi',
    summary: 'Ortiqcha vaznni boshqarishda muvozanatli ovqatlanish va odatlarni o‘zgartirishga qaratilgan.',
    principle: 'Barqaror, xavfsiz o‘zgarishlar keskin och qolishdan afzal; kaloriya ehtiyoji individual.',
    foods: ['Sabzavotlar va tolaga boy mahsulotlar', 'Oqsil manbalari', 'Me’yoriy porsiyalar va suv'],
    limit: 'Shirin ichimliklar, tez-tez iste’mol qilinadigan yuqori kaloriyali yeguliklar.',
    mealIdeas: 'Sabzavot va oqsil manbali likopcha, meva bilan shakarsiz qatiq.'
  },
  {
    number: '9',
    name: 'Qondagi glyukozani hisobga oluvchi ovqatlanish',
    category: 'Moddalar almashinuvi',
    summary: 'Qandli diabetda ovqatlanish rejasi dori yoki insulin bilan birga individual tuziladi.',
    principle: 'Uglevodlarni hisoblash va ovqatlanish vaqti davolash rejasiga mos bo‘lishi kerak.',
    foods: ['Sabzavotlar va tolaga boy mahsulotlar', 'Shifokor belgilagan uglevod porsiyalari', 'Muvozanatli oqsil manbalari'],
    limit: 'Shirin ichimliklar va tez so‘riluvchi shakar; uglevodlarni butunlay chiqarib tashlash tavsiya etilmaydi.',
    mealIdeas: 'Sabzavot, oqsil va o‘lchangan donli garnirdan iborat muvozanatli taom.'
  },
  {
    number: '10',
    name: 'Yurak-qon tomir salomatligiga mos ovqatlanish',
    category: 'Yurak va tiklanish',
    summary: 'Yurak-qon tomir kasalliklarida tuz va yog‘ miqdori shifokor tavsiyasiga qarab nazorat qilinadi.',
    principle: 'Muvozanatli ratsion, tuzni me’yorlash va muntazam kuzatuv muhim.',
    foods: ['Sabzavot va mevalar', 'Butun don mahsulotlari', 'Yog‘siz oqsil manbalari'],
    limit: 'Ortiqcha tuz, trans-yog‘ va juda ko‘p qayta ishlangan mahsulotlar.',
    mealIdeas: 'Sabzavotli sho‘rva, dimlangan baliq, ko‘katli grechka.'
  },
  {
    number: '11',
    name: 'Tiklanish davrida quvvatli ovqatlanish',
    category: 'Yurak va tiklanish',
    summary: 'Ayrim tiklanish davrlarida energiya va oqsil ehtiyoji oshishi mumkin.',
    principle: 'Miqdor va mahsulotlar kasallik, ishtaha va davolash holatiga qarab tanlanadi.',
    foods: ['Oqsilga boy mahsulotlar', 'Yormalar va sabzavotlar', 'Energiya beruvchi muvozanatli taomlar'],
    limit: 'O‘zboshimchalik bilan qo‘shimcha yoki juda yog‘li taomlar bilan vazn oshirish.',
    mealIdeas: 'Tuxum yoki tvorog, yorma garniri va sabzavotlardan tuzilgan to‘yimli taom.'
  },
  {
    number: '12',
    name: 'Asab tizimiga mos yengil ovqatlanish',
    category: 'Umumiy',
    summary: 'Bu raqam eski parhez tasnifida qo‘llanadi; hozirgi klinik tavsiyalarda alohida standart sifatida kam ishlatiladi.',
    principle: 'Uyqu, kofein va umumiy ovqatlanish odatlari shaxsiy simptomlarga qarab ko‘rib chiqiladi.',
    foods: ['Muvozanatli kundalik taomlar', 'Sabzavot, meva va donlar', 'Yetarli suyuqlik'],
    limit: 'Kofeinni ko‘p iste’mol qilish simptomlarni kuchaytirsa, miqdorini shifokor bilan muhokama qiling.',
    mealIdeas: 'Muntazam va muvozanatli nonushta, tushlik hamda kechki ovqat.'
  },
  {
    number: '13',
    name: 'O‘tkir infeksiya davrida ovqatlanish',
    category: 'Yurak va tiklanish',
    summary: 'O‘tkir infeksiyada ovqatlanish holatga va bemorning ko‘tara olishiga moslashtiriladi.',
    principle: 'Suyuqlik ichish va yengil, to‘yimli taomlar muhim; suyuqlik cheklovi bo‘lsa, shifokorga amal qiling.',
    foods: ['Yengil sho‘rva va bo‘tqalar', 'Oqsil manbali yumshoq taomlar', 'Shifokor tavsiya qilgan ichimliklar'],
    limit: 'Ishtaha yo‘qligida majburlab ko‘p yedirish yoki shifokorsiz qo‘shimcha preparat berish.',
    mealIdeas: 'Yengil sho‘rva, yumshoq bo‘tqa, oz-ozdan tez-tez ovqatlanish.'
  },
  {
    number: '14',
    name: 'Siydik-tosh kasalligida individual ratsion',
    category: 'Jigar va buyrak',
    summary: 'Siydik tarkibi va tosh turi ma’lum bo‘lgandagina mos ovqatlanish belgilanadi.',
    principle: 'Tosh turiga qarab tavsiyalar bir-biridan farq qiladi; umumiy ro‘yxat xavfsiz bo‘lmasligi mumkin.',
    foods: ['Tosh turi va tahlillarga mos mahsulotlar', 'Shifokor ruxsat bergan suyuqlik miqdori'],
    limit: 'Mahsulotlarni tahlilsiz cheklamang; ayrim tavsiyalar turli toshlarda qarama-qarshi bo‘lishi mumkin.',
    mealIdeas: 'Nefrolog yoki urolog tuzgan shaxsiy menyu.'
  },
  {
    number: '15',
    name: 'Umumiy muvozanatli ovqatlanish',
    category: 'Umumiy',
    summary: 'Maxsus davolovchi cheklov talab qilinmagan holatlarda qo‘llanadigan umumiy ratsion tamoyillari.',
    principle: 'Turli xil mahsulotlar, me’yoriy porsiyalar va muntazam ovqatlanishga e’tibor beriladi.',
    foods: ['Sabzavot va mevalar', 'Don, oqsil va sut mahsulotlarining mos turlari', 'Yetarli suv'],
    limit: 'Bir xil mahsulot bilan cheklanish va ortiqcha shakar, tuz yoki yog‘.',
    mealIdeas: 'Sabzavotli sho‘rva, donli garnir va oqsil manbali taom.'
  }
]

const categories = ['Barchasi', ...new Set(dietTables.map((table) => table.category))]

const DietTables = () => {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('Barchasi')
  const [savedOnly, setSavedOnly] = useState(false)
  const [savedTables, setSavedTables] = useState([])
  const [expandedTable, setExpandedTable] = useState(null)

  const visibleTables = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase('uz-UZ')
    return dietTables.filter((table) => {
      const matchesCategory = category === 'Barchasi' || table.category === category
      const matchesSaved = !savedOnly || savedTables.includes(table.number)
      const searchableText = [
        table.number,
        table.name,
        table.summary,
        table.category,
        table.principle,
        ...table.foods,
        table.limit,
        table.mealIdeas
      ].join(' ').toLocaleLowerCase('uz-UZ')
      return matchesCategory && matchesSaved && (!normalizedQuery || searchableText.includes(normalizedQuery))
    })
  }, [category, query, savedOnly, savedTables])

  const toggleSaved = (tableNumber) => {
    setSavedTables((current) => current.includes(tableNumber)
      ? current.filter((number) => number !== tableNumber)
      : [...current, tableNumber])
  }

  return (
    <section className="diet-guide" aria-labelledby="diet-guide-title">
      <header className="diet-guide-hero">
        <div className="diet-guide-hero-copy">
          <span className="diet-guide-eyebrow">SOG‘LOM OVQATLANISH QO‘LLANMASI</span>
          <h2 id="diet-guide-title">Parhez stollari</h2>
          <p>Turli holatlarda tavsiya etiladigan ovqatlanish tamoyillari va yengil taom g‘oyalarini o‘rganing.</p>
        </div>
        <div className="diet-guide-hero-icon" aria-hidden="true">🥗</div>
        <div className="diet-guide-stats">
          <strong>{dietTables.length}</strong>
          <span>parhez yo‘nalishi</span>
        </div>
      </header>

      <div className="diet-guide-notice" role="note">
        <span aria-hidden="true">ℹ️</span>
        <p>
          Bu sahifa umumiy maʼlumot beradi. Parhez stollari tarixiy tasnifga asoslangan;
          sizga mos ratsionni tashxis va tahlillaringizni biladigan shifokor belgilaydi.
          Ayniqsa buyrak, diabet yoki yurak kasalliklarida mahsulotlarni o‘zboshimchalik bilan cheklamang.
        </p>
      </div>

      <div className="diet-guide-tools">
        <label className="diet-search">
          <span aria-hidden="true">⌕</span>
          <span className="sr-only">Parhez yoki taom bo‘yicha qidirish</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Parhez raqami, holat yoki taomni qidiring"
          />
          {query && (
            <button type="button" onClick={() => setQuery('')} aria-label="Qidiruvni tozalash">×</button>
          )}
        </label>
        <button
          type="button"
          className={`diet-saved-toggle ${savedOnly ? 'active' : ''}`}
          aria-pressed={savedOnly}
          onClick={() => setSavedOnly((current) => !current)}
        >
          {savedOnly ? '★ Saqlanganlar' : '☆ Saqlanganlar'}
          <span>{savedTables.length}</span>
        </button>
      </div>

      <div className="diet-category-list" aria-label="Parhez yo‘nalishini tanlang">
        {categories.map((item) => (
          <button
            type="button"
            key={item}
            className={`diet-category-chip ${category === item ? 'active' : ''}`}
            aria-pressed={category === item}
            onClick={() => setCategory(item)}
          >
            {item}
          </button>
        ))}
      </div>

      <p className="diet-results-count">{visibleTables.length} ta parhez yo‘nalishi</p>

      {visibleTables.length ? (
        <div className="diet-card-grid">
          {visibleTables.map((table) => {
            const isExpanded = expandedTable === table.number
            const isSaved = savedTables.includes(table.number)
            return (
              <article className={`diet-card ${isExpanded ? 'expanded' : ''}`} key={table.number}>
                <div className="diet-card-topline">
                  <span className="diet-number">№ {table.number}</span>
                  <button
                    type="button"
                    className={`diet-save-button ${isSaved ? 'saved' : ''}`}
                    aria-label={isSaved ? `${table.name} saqlanganlardan olib tashlash` : `${table.name}ni saqlanganlarga qo‘shish`}
                    aria-pressed={isSaved}
                    onClick={() => toggleSaved(table.number)}
                  >
                    {isSaved ? '★' : '☆'}
                  </button>
                </div>
                <span className="diet-card-category">{table.category}</span>
                <h3>{table.name}</h3>
                <p className="diet-card-summary">{table.summary}</p>
                <button
                  type="button"
                  className="diet-details-toggle"
                  aria-expanded={isExpanded}
                  onClick={() => setExpandedTable(isExpanded ? null : table.number)}
                >
                  {isExpanded ? 'Tafsilotni yopish' : 'Taomlar va tavsiyalar'}
                  <span aria-hidden="true">{isExpanded ? '−' : '+'}</span>
                </button>
                {isExpanded && (
                  <div className="diet-card-details">
                    <div>
                      <h4>Asosiy tamoyil</h4>
                      <p>{table.principle}</p>
                    </div>
                    <div>
                      <h4>Odatda tanlanadi</h4>
                      <ul>{table.foods.map((food) => <li key={food}>{food}</li>)}</ul>
                    </div>
                    <div className="diet-limit-note">
                      <h4>Nimalarga eʼtibor berish kerak</h4>
                      <p>{table.limit}</p>
                    </div>
                    <div className="diet-meal-idea">
                      <h4>🍲 Taom g‘oyasi</h4>
                      <p>{table.mealIdeas}</p>
                    </div>
                  </div>
                )}
              </article>
            )
          })}
        </div>
      ) : (
        <div className="diet-empty-state">
          <span aria-hidden="true">🥣</span>
          <h3>{savedOnly && savedTables.length === 0 ? 'Hali saqlangan parhez yo‘q' : 'Mos parhez topilmadi'}</h3>
          <p>{savedOnly && savedTables.length === 0 ? 'Yoqtirgan parhezingizdagi yulduzchani bosing — u shu sahifada saqlanadi.' : 'Qidiruv so‘zini o‘zgartiring yoki boshqa yo‘nalishni tanlang.'}</p>
          {(query || category !== 'Barchasi' || savedOnly) && (
            <button
              type="button"
              onClick={() => {
                setQuery('')
                setCategory('Barchasi')
                setSavedOnly(false)
              }}
            >
              Filtrlarni tozalash
            </button>
          )}
        </div>
      )}
    </section>
  )
}

export default DietTables
