/* Holotique dil desteği
 * Sayfalar Türkçe yazılır; seçilen dil Türkçe değilse bu dosya ekrandaki metinleri
 * (dinamik olanlar dahil) sözlükten çevirir. Yeni bir dil eklemek için DICT'e bir sözlük eklemek yeterli.
 * Kullanıcı verileri (kart adları, klasör adları) çevrilmez: yalnızca sözlükteki ifadeler değişir.
 */
(function () {
  'use strict';
  var LANGS = [['tr', 'TR', 'Türkçe'], ['en', 'EN', 'English']];
  var store = { get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
                set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} } };
  var saved = store.get('hq-lang');
  var LANG = saved || ((navigator.language || 'tr').toLowerCase().indexOf('tr') === 0 ? 'tr' : 'en');
  if (!LANGS.some(function (l) { return l[0] === LANG; })) LANG = 'en';
  window.HQ_LANG = LANG;
  document.documentElement.lang = LANG;

  var MONTHS_TR = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
  var MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  var DICT = {};
  DICT.en = {
    exact: {
      // ortak
      'Holotique · Kart fiyatları ve arama': 'Holotique · Card prices & search',
      'Holotique · Kart portföyü': 'Holotique · Card portfolio',
      'Gizlilik · Holotique': 'Privacy · Holotique',
      'Kart ara': 'Search cards', 'Portföyüm': 'My portfolio', 'Yönetim': 'Admin', 'Gizlilik': 'Privacy',
      'Sayfalar': 'Pages', 'İkinci para birimi': 'Second currency', 'Ana fiyat her zaman USD': 'Main price is always USD',
      'Yükleniyor': 'Loading', 'Yükleniyor…': 'Loading…', 'Kapat': 'Close', 'Temizle': 'Clear', 'Tümü': 'All',
      'Sırala': 'Sort', 'Oyun': 'Game', 'Düzenle': 'Edit', 'Vazgeç': 'Cancel', 'Kaydet': 'Save', 'Ekle': 'Add',
      'Görsel yok': 'No image', 'Bağlantı kurulamadı. Sayfayı yenile.': 'Could not connect. Please refresh the page.',
      'TCGplayer’da gör': 'View on TCGplayer', 'Portföyüme ekle': 'Add to my portfolio',
      'Pokemon (Japonca)': 'Pokemon (Japanese)', 'Japonca': 'Japanese', 'İngilizce': 'English',
      'yüksek': 'high', 'orta': 'medium', 'düşük': 'low', 'takip edilmiyor': 'not tracked', 'satış yok': 'no sales',
      'Ham': 'Raw', 'Ham · piyasa': 'Raw · market', 'Ham (derecesiz)': 'Raw (ungraded)', 'Ham değer': 'Raw value',
      'Fiyat geçmişi': 'Price history', 'Fiyat geçmişi birikiyor.': 'Price history is building up.', 'Fiyat geçmişi yok.': 'No price history.',

      // arama sayfası
      'Kartın ne kadar ediyor?': 'What is your card worth?',
      'Pokemon, Japon Pokemon, One Piece, Magic, Riftbound ve Lorcana kartlarını adıyla, setiyle ya da numarasıyla ara. Fiyatlar her gün güncellenir, üyelik gerekmez.':
        'Search Pokemon, Japanese Pokemon, One Piece, Magic, Riftbound and Lorcana cards by name, set or number. Prices update daily, no sign-up needed.',
      'Kart adı, set ya da numara': 'Card name, set or number',
      'Set / seri: tümü ▾': 'Set / series: all ▾', 'Set adı, kodu ya da yılı': 'Set name, code or year', 'Set ara': 'Search sets',
      'Set filtresini kaldır': 'Remove set filter', 'Setler': 'Sets', 'Sonuçlar': 'Results',
      'En uygun': 'Best match', 'En değerli': 'Most valuable', 'En ucuz': 'Cheapest', 'Yeni setler önce': 'Newest sets first',
      'Set ve kart numarası': 'Set and card number',
      'İpucu: ad + numara': 'Tip: name + number', '· ad + set': '· name + set', '· numara': '· number', '· set kodu': '· set code',
      'Son aramalar': 'Recent searches', 'Son baktıkların': 'Recently viewed', 'Daha fazla göster': 'Show more',
      'Aranıyor…': 'Searching…', 'En değerli kartlar': 'Most valuable cards', 'Sete göre daralt': 'Narrow by set', 'Tüm setler': 'All sets',
      'Bu sette ara': 'Search in this set', 'Setler yükleniyor…': 'Loading sets…', 'Set bulunamadı.': 'No set found.', 'Setler alınamadı.': 'Could not load sets.',
      'Set filtresi yakında.': 'Set filter coming soon.',
      'Sonuç bulunamadı': 'No results',
      'Bu sette aramana uyan kart yok. Set filtresini kaldırıp tekrar dene.': 'No cards in this set match your search. Remove the set filter and try again.',
      'Daha az kelimeyle dene: yalnızca kart adı, ya da ad + numara (ör. charizard 4).': 'Try fewer words: just the card name, or name + number (e.g. charizard 4).',
      'Katalog hazırlanıyor': 'Catalog is being prepared', 'Katalog henüz hazır değil.': 'Catalog is not ready yet.',
      'Kart listesi her gece güncellenir. Biraz sonra tekrar dene.': 'The card list updates every night. Please try again shortly.',
      'Nadirlik': 'Rarity', 'Baskı': 'Printing', 'En düşük ilan': 'Lowest listing', 'Fiyat tarihi': 'Price date',
      'PSA fiyatları ve fiyat geçmişi, kart bir Holotique portföyüne eklendiğinde takip edilmeye başlar.':
        'PSA prices and price history start being tracked once the card is added to a Holotique portfolio.',
      'Ham fiyatlar: TCGplayer piyasa fiyatı (TCGCSV aracılığıyla), günlük. PSA fiyatları: eBay satışları (PokemonPriceTracker), yalnızca Holotique portföylerinde takip edilen kartlar için. Yatırım tavsiyesi değildir.':
        'Raw prices: TCGplayer market price (via TCGCSV), daily. PSA prices: eBay sales (PokemonPriceTracker), only for cards tracked in Holotique portfolios. Not investment advice.',
      '· Aramalar ve görüntülenen kartlar kişiyle ilişkilendirilmeden, anonim olarak sayılır.': '· Searches and viewed cards are counted anonymously, never linked to a person.',

      // portföy: giriş
      'Koleksiyonunu portföy gibi izle': 'Track your collection like a portfolio',
      'Ham ve PSA fiyatları her gün güncellenir. Alış fiyatların ve sertifika numaraların yalnızca sana görünür.':
        'Raw and PSA prices update daily. Your purchase prices and cert numbers are visible only to you.',
      'Giriş yap': 'Sign in', 'Hesap aç': 'Create account', 'E-posta': 'Email', 'Şifre': 'Password', 'En az 8 karakter': 'At least 8 characters',
      'ornek@eposta.com': 'you@example.com',
      'Şifreni mi unuttun? E-postana giriş bağlantısı gönderelim': 'Forgot your password? We’ll email you a sign-in link',
      'Portföyün veritabanı düzeyinde korunur: başka hiçbir kullanıcı senin kartlarını, alış fiyatlarını ya da PSA numaralarını göremez.':
        'Your portfolio is protected at the database level: no other user can see your cards, purchase prices or PSA numbers.',
      'E-posta ya da şifre hatalı.': 'Wrong email or password.',
      'E-posta adresin henüz onaylanmadı. Gelen kutundaki bağlantıya tıkla.': 'Your email isn’t confirmed yet. Click the link in your inbox.',
      'Bu e-postayla zaten bir hesap var. Giriş yap sekmesini kullan.': 'An account with this email already exists. Use the Sign in tab.',
      'Çok fazla deneme yapıldı. Biraz bekleyip tekrar dene.': 'Too many attempts. Please wait a bit and try again.',
      'Şifre en az 8 karakter olmalı.': 'Password must be at least 8 characters.',
      'Hesabın oluşturuldu. E-postana gelen onay bağlantısına tıkla, sonra buradan giriş yap.': 'Your account was created. Click the confirmation link in your email, then sign in here.',
      'Önce e-posta adresini yaz.': 'Enter your email first.', 'Giriş bağlantısı e-postana gönderildi.': 'A sign-in link was sent to your email.',
      'Çıkış': 'Sign out', 'Çıkış yaptın.': 'You signed out.',

      // portföy: pano
      'Portföy değeri': 'Portfolio value', 'Portföy değeri, USD': 'Portfolio value, USD', 'Portföy': 'Portfolio',
      'Maliyet (fiyatlı kartlar)': 'Cost (priced cards)', 'K/Z': 'P/L', 'Son değişim': 'Last change',
      'İkinci gün kaydından sonra': 'After the second daily record', 'Derece dağılımı': 'Grade mix', 'Zaman aralığı': 'Time range',
      'Fiyat geçmişi her gün birikiyor; grafik birkaç gün içinde dolacak.': 'Price history builds up daily; the chart will fill in over a few days.',
      'Portföy değeri grafiği': 'Portfolio value chart', 'Kart fiyat grafiği': 'Card price chart', 'Fiyat grafiği': 'Price chart',
      'Henüz fiyat kaydı yok.': 'No price records yet.',
      'Değere göre': 'By value', 'K/Z yüzdesine göre': 'By P/L %', '7 günlük değişime göre': 'By 7-day change', 'Ada göre': 'By name', 'Duruma göre': 'By status',
      'Excel’den yükle': 'Import from Excel', 'Excel’den içe aktar': 'Import from Excel', 'Kart ekle': 'Add card', 'Tek kart ekle': 'Add a single card',
      'Fiyatlar her gün otomatik güncellenir. Yeni kartlar birkaç saat içinde eşleşir.': 'Prices update automatically every day. New cards are matched shortly.',
      'Portföyün boş': 'Your portfolio is empty',
      'Kartlarını Excel dosyasından toplu olarak yükleyebilir ya da tek tek ekleyebilirsin. Eklediğin kartlar birkaç saat içinde katalogla eşleşir ve fiyatlanır.':
        'You can import your cards from an Excel file or add them one by one. Added cards are matched to the catalog and priced shortly.',
      'Eşleştiriliyor': 'Matching', 'Bulunamadı': 'Not found', 'Desteklenmiyor': 'Not supported', 'Derece desteklenmiyor': 'Grade not supported',
      'Fiyat bekleniyor': 'Awaiting price', 'Kontrol et': 'Check', 'Düşük güven': 'Low confidence', 'Yaklaşık değer': 'Approximate value',
      'Bu derecede satış yok': 'No sales at this grade',
      'Bu kartın bu derecesi için son 6 ayda eBay satışı bulunamadı.': 'No eBay sales found for this card at this grade in the last 6 months.',
      'Bu oyun için dereceli (PSA) fiyat kaynağı henüz yok; ham piyasa değeri gösteriliyor.': 'No graded (PSA) price source for this game yet; showing raw market value.',
      'Bu kart katalogla eşleştirilmeyi bekliyor. Genellikle birkaç saat içinde eşleşir.': 'This card is waiting to be matched to the catalog. This usually happens within a few hours.',
      'Kart eşleştirilemedi.': 'The card could not be matched.',
      'Adet': 'Qty', 'Alış (adet)': 'Cost (each)', 'Alış tarihi': 'Purchase date', 'Sertifika no': 'Cert no', 'sertifika no': 'cert no',
      'PSA kaydı': 'PSA record', 'PSA etiketi': 'PSA label', 'PSA derecesi': 'PSA grade', 'Bu derecede popülasyon': 'Population at this grade', 'Üst derecede': 'Graded higher',
      'Bu PSA numarası için PSA kaydı bulunamadı. Numarayı kontrol et.': 'No PSA record was found for this PSA number. Please check the number.',
      'PSA numarası ve alış bilgileri yalnızca sana görünür. “PSA’da doğrula” kartın PSA kaydını, görsellerini ve popülasyonunu PSA’nın kendi sitesinde açar.':
        'Your PSA number and purchase details are visible only to you. “Verify at PSA” opens the card’s PSA record, images and population on PSA’s own site.',
      'PSA’da doğrula': 'Verify at PSA', 'CGC’da doğrula': 'Verify at CGC', 'Görsel': 'Image', 'Katalog': 'Catalog', 'PSA ön': 'PSA front', 'PSA arka': 'PSA back',
      'Kartı sil': 'Delete card', 'Silmek için tekrar bas': 'Press again to delete',
      'Grading masası': 'Grading desk', 'Ham, PSA 9 ve PSA 10 fiyatları güncel piyasadan gelir. Olasılıklar senin tahminin.':
        'Raw, PSA 9 and PSA 10 prices come from the current market. The probabilities are your estimate.',
      'Ham fiyat $': 'Raw price $', 'Grading + kargo $': 'Grading + shipping $', 'PSA 10 fiyatı $': 'PSA 10 price $', 'PSA 10 olasılığı %': 'PSA 10 chance %',
      'PSA 9 fiyatı $': 'PSA 9 price $', 'PSA 9 olasılığı %': 'PSA 9 chance %', 'PSA 8 ve altı $': 'PSA 8 or lower $', 'PSA 8 ve altı %': 'PSA 8 or lower %',
      'Beklenen kazanç': 'Expected gain', 'Grade ettir': 'Get it graded', 'Ham sat': 'Sell raw', 'Beklenen satış değeri': 'Expected sale value',
      'Başa baş PSA 10 olasılığı': 'Break-even PSA 10 chance', '%100 üstü': 'over 100%',
      // kart ekleme formu
      'Kartı düzenle': 'Edit card', 'Kart adı': 'Card name', 'Set': 'Set', 'Kart numarası': 'Card number', 'Dil': 'Language', 'Derece': 'Grade',
      'Alış fiyatı $ (adet)': 'Purchase price $ (each)', 'isteğe bağlı': 'optional', 'ör. Terastal Festival': 'e.g. Terastal Festival',
      'ör. Umbreon ex': 'e.g. Umbreon ex', 'ör. 217': 'e.g. 217',
      'Kartın sol ya da sağ alt köşesindeki numarayı yazmak eşleşmeyi hızlandırır. Kart birkaç saat içinde fiyatlanır.':
        'Entering the number from the card’s bottom corner speeds up matching. The card will be priced shortly.',
      // içe aktarma
      'Excel ya da CSV dosyanı seç': 'Choose your Excel or CSV file',
      'Sütun adları ve sırası önemli değil: kart adı, set, numara, dil, derece, PSA numarası, adet, alış fiyatı (USD) ve alış tarihini otomatik tanırız.':
        'Column names and order don’t matter: we detect card name, set, number, language, grade, PSA number, quantity, purchase price (USD) and purchase date automatically.',
      'Alış fiyatlarının USD olduğu varsayılır.': 'Purchase prices are assumed to be in USD.', 'İlk 8 satır gösteriliyor.': 'Showing the first 8 rows.',
      'Excel okuyucu yüklenemedi. Sayfayı yenileyip tekrar dene.': 'The Excel reader failed to load. Refresh the page and try again.',
      'Kart adı sütunu bulunamadı. İlk satırda "Kart adı" ya da "Card name" gibi bir başlık olduğundan emin ol.':
        'No card name column found. Make sure the first row has a header like "Card name".',
      'Aktarılıyor…': 'Importing…', 'Kart': 'Card', 'Alış': 'Cost',
      // klasörler
      'Tüm kartlar': 'All cards', '+ Yeni klasör': '+ New folder', 'Yeni klasör': 'New folder', 'Klasörler': 'Folders',
      'Kartlarını klasörlere ayır: “PSA 10’lar”, “Satılık”, “Charizard koleksiyonu” gibi. Bir kart birden fazla klasörde olabilir.':
        'Sort your cards into folders like “PSA 10s”, “For sale” or “Charizard collection”. A card can be in more than one folder.',
      'Değer, K/Z ve grafik yalnızca bu klasördeki kartları gösteriyor.': 'Value, P/L and the chart only show cards in this folder.',
      'Kart ekle / çıkar': 'Add / remove cards', 'Adını değiştir': 'Rename', 'Klasör adı': 'Folder name',
      'ör. PSA 10’lar, Satılık, Japon kartlar': 'e.g. PSA 10s, For sale, Japanese cards', 'Kartları seç': 'Choose cards',
      'Dereceye göre': 'By grade', 'Diğer dereceli': 'Other graded', 'Ham (raw)': 'Raw', 'Kartlarda ara': 'Search your cards', 'Tüm oyunlar': 'All games',
      'Sadece seçililer': 'Selected only', 'Görünenlerin hepsini seç': 'Select all shown', 'Görünenleri bırak': 'Unselect shown',
      'Bu filtreye uyan kart yok.': 'No cards match this filter.', 'Klasörü oluştur': 'Create folder', 'Klasörü sil': 'Delete folder',
      'Silmek için tekrar bas (kartlar silinmez)': 'Press again to delete (cards are kept)', 'Klasöre bir ad ver.': 'Give the folder a name.',
      'Bu adla bir klasörün zaten var.': 'You already have a folder with this name.', 'Bu klasör boş': 'This folder is empty',
      'Kartlarını filtreleyip bu klasöre ekleyebilirsin.': 'Filter your cards and add them to this folder.',
      'Fiyatlar: PokemonPriceTracker aracılığıyla TCGplayer (ham) ve eBay satışları (PSA). PSA fiyatı son 7 günün ağırlıklı satış fiyatıdır; güven düzeyi satış adedine göre belirlenir. Kurlar: Avrupa Merkez Bankası (Frankfurter). Yatırım tavsiyesi değildir.':
        'Prices: TCGplayer (raw) and eBay sales (PSA) via PokemonPriceTracker. The PSA price is the weighted sale price of the last 7 days; confidence depends on the number of sales. FX rates: European Central Bank (Frankfurter). Not investment advice.',
      '· Alış fiyatların ve sertifika numaraların yalnızca sana görünür.': '· Your purchase prices and cert numbers are visible only to you.',
      'Uygulamayı yükle': 'Install app',
      'Hedef fiyata inince bana mail at': 'Email me when it hits my target price',
      'Kart hedef fiyatına ya da altına indiğinde bir kez haber veririz. Fiyat yeniden yükselip tekrar inerse yine haber veririz.': 'We’ll let you know once when the card drops to or below your target. If the price rises and drops again, we’ll tell you again.',
      'Satılık': 'For sale',
      'Satıldı': 'Sold',
      'Satış fiyatı': 'Asking price',
      'piyasa fiyatında': 'at market price',
      'WhatsApp’tan sor': 'Ask on WhatsApp',
      'Instagram’dan yaz': 'Message on Instagram',
      'Satılık kartlar': 'Cards for sale',
      'Satış fiyatı (adet)': 'Asking price (each)',
      'Para birimi': 'Currency',
      'Satış notu (vitrinde görünür)': 'Sale note (shown on showcase)',
      'ör. Köşelerde hafif beyazlama, kargo alıcıya': 'e.g. Light corner whitening, buyer pays shipping',
      'Vitrininde satış fiyatıyla görünür; alıcılar sana WhatsApp ya da Instagram’dan yazar.': 'Shown on your showcase with your price; buyers contact you on WhatsApp or Instagram.',
      'Satıldı olarak işaretle': 'Mark as sold',
      'Satıştan kaldır': 'Remove from sale',
      'Satışa geri al': 'Put back on sale',
      'Satışa çıkar': 'Put up for sale',
      'Satıldı olarak işaretlendi. Vitrinde 14 gün “Satıldı” etiketiyle görünür. Kart artık sende değilse portföyden silebilirsin.': 'Marked as sold. It stays on your showcase with a “Sold” label for 14 days. If you no longer have the card, you can delete it from your portfolio.',
      'Yalnızca satılık kartlar': 'Only cards for sale',
      'Satılık kartlarda piyasa referansını göster': 'Show market reference on cards for sale',
      'Alıcı, senin fiyatının yanında piyasa değerini görür. Referans, fiyatı yazdığın para birimine çevrilir.': 'Buyers see the market value next to your price, converted to the currency you priced in.',
      'ör. +90 555 123 45 67': 'e.g. +90 555 123 45 67',
      'ör. @kullaniciadi': 'e.g. @username',
      'WhatsApp numarası (satılık kartlarda “WhatsApp’tan sor” düğmesi)': 'WhatsApp number (“Ask on WhatsApp” button on cards for sale)',
      'Instagram kullanıcı adı (“Instagram’dan yaz” düğmesi)': 'Instagram username (“Message on Instagram” button)',
      'WhatsApp numarasını ülke koduyla yaz (ör. +90 555 123 45 67).': 'Enter the WhatsApp number with country code (e.g. +90 555 123 45 67).',
      'Instagram kullanıcı adı geçersiz.': 'Invalid Instagram username.',
      'Görselde ne olsun?': 'What should the image show?',
      'SATILIK': 'FOR SALE',
      'satılık kart': 'cards for sale',
      'Satıcı fiyatı · alım satım taraflar arasında': 'Seller’s price · deal is between buyer and seller',
      'Değerler TCGplayer piyasa fiyatlarından ve eBay satışlarından hesaplanan tahminlerdir. Satış fiyatlarını satıcı belirler; Holotique alım satıma aracılık etmez, ödeme almaz, kartların sahipliğini ve durumunu doğrulamaz. Yatırım tavsiyesi değildir.': 'Values are estimates based on TCGplayer market prices and eBay sales. Asking prices are set by the seller; Holotique does not broker sales, take payments, or verify ownership or condition of the cards. Not investment advice.',
      'Vitrinin adı': 'Showcase name',
      'Bağlantın': 'Your link',
      'Vitrine bir ad ver.': 'Give your showcase a name.',
      'Baştaki kod sana özel ve rastgele; sondaki kısım vitrinin adından oluşur. Adı değiştirsen de eski bağlantılar çalışmaya devam eder.': 'The code at the start is random and unique to you; the last part comes from your showcase name. Old links keep working even if you rename it.',
      'Veritabanı güncellemesi eksik (013_showcase_code.sql).': 'Database update missing (013_showcase_code.sql).',
      'VİTRİN': 'SHOWCASE',
      'kart': 'cards',
      'Tahmini piyasa değeri': 'Estimated market value',
      'Vitrin görseli': 'Showcase image',
      'En değerli kartlarından otomatik bir görsel: Instagram’da gönderi ya da hikâye olarak paylaşabilirsin. Vitrin ayarların (klasör, değerleri göster) görsele de uygulanır.': 'An automatic image of your most valuable cards to share as an Instagram post or story. Your showcase settings (folder, show values) also apply to the image.',
      'Görsel boyutu': 'Image size',
      'Gönderi 4:5': 'Post 4:5',
      'Hikâye 9:16': 'Story 9:16',
      'Görsel hazırlanıyor…': 'Preparing image…',
      'Görseli indir': 'Download image',
      'Görsel kaydedilemedi. Sayfayı yenileyip tekrar dene.': 'Could not save the image. Refresh the page and try again.',
      'Görsel olarak paylaş': 'Share as image',
      'Kart sayısı': 'Cards',
      'Vitrin · Holotique': 'Showcase · Holotique',
      'Bölümler': 'Sections',
      'İstek listesi': 'Wishlist',
      'Vitrin': 'Showcase',
      'Takip ettiğin kartlar burada': 'Cards you’re watching live here',
      'Almak istediğin kartları ekle, fiyatlarını her gün izleyelim. Bir hedef fiyat yazarsan kart o fiyata indiğinde listede işaretlenir. İstersen listeni vitrininde “Aradığım kartlar” olarak da gösterebilirsin.': 'Add cards you want to buy and we’ll track their prices every day. Set a target price and the card is flagged when it drops to it. You can also show your list on your showcase as “Cards I’m looking for”.',
      'Kart ara ve ekle': 'Search and add a card',
      'Arama sayfasına git': 'Go to search',
      'Hedef fiyatta': 'At target price',
      'hedef yok': 'no target',
      'Eklediğinden bu yana': 'Since you added it',
      'Yüzde, kartı listeye eklediğin günden bu yana fiyat değişimini gösterir (düşüş yeşil). Dereceli fiyatlar eklendikten sonraki ilk fiyat güncellemesinde gelir.': 'The percentage shows the price change since you added the card (a drop is green). Graded prices arrive with the first price update after adding.',
      'Hedef fiyat $': 'Target price $',
      'Not': 'Note',
      'İstek listeme ekle': 'Add to my wishlist',
      '☆ İstek listeme ekle': '☆ Add to wishlist',
      'Bu oyun için yalnızca ham fiyat takip edilebiliyor.': 'Only raw prices can be tracked for this game.',
      'Bu kart bu dereceyle zaten istek listende.': 'This card is already on your wishlist at this grade.',
      'İstek listesine ekle': 'Add to wishlist',
      'Listeden çıkar': 'Remove from list',
      'Çıkarmak için tekrar bas': 'Press again to remove',
      'Aldım, portföye taşı': 'Bought it — move to portfolio',
      'Koleksiyonunu bir bağlantıyla paylaş: Instagram’da, forumlarda ya da takas gruplarında. Vitrinde kartlar, dereceler, adetler ve istersen güncel piyasa değeri görünür. Alış fiyatların, alış tarihlerin, sertifika numaraların ve e-posta adresin asla görünmez.': 'Share your collection with a link — on Instagram, forums or trading groups. The showcase shows cards, grades, quantities and, if you like, current market value. Your purchase prices, purchase dates, cert numbers and email are never shown.',
      'Bağlantıyı kopyala': 'Copy link',
      'Kopyalandı': 'Copied',
      'Paylaş': 'Share',
      'Yayında': 'Live',
      'Vitrini aç': 'Open showcase',
      'ör. berk-tcg': 'e.g. berk-tcg',
      'Bu adres alınmış.': 'This address is taken.',
      'Adres uygun.': 'Address available.',
      'ör. Berk’in Pokemon koleksiyonu': 'e.g. Berk’s Pokemon collection',
      'ör. Instagram @kullaniciadi': 'e.g. Instagram @username',
      'Değerleri göster': 'Show values',
      'Her kartın ve vitrinin toplam güncel piyasa değeri. Kapalıyken yalnızca kartlar görünür.': 'Current market value of each card and the showcase total. When off, only the cards are shown.',
      '“Aradığım kartlar” bölümünü göster': 'Show the “Cards I’m looking for” section',
      'İstek listendeki kartlar (hedef fiyatların görünmez).': 'Cards on your wishlist (your target prices stay hidden).',
      'Vitrin yayında': 'Showcase is live',
      'Kapatırsan bağlantı hemen çalışmaz olur.': 'If you turn it off, the link stops working immediately.',
      'Vitrini oluştur': 'Create showcase',
      'Vitrin adresi': 'Showcase address',
      'Başlık': 'Title',
      'Hakkında': 'About',
      'İletişim (isteğe bağlı, herkese görünür)': 'Contact (optional, visible to everyone)',
      'Hangi kartlar görünsün?': 'Which cards should be shown?',
      'Adres 3–24 karakter olmalı; harf, rakam, - ve _ kullanılabilir.': 'The address must be 3–24 characters: letters, numbers, - and _.',
      'Bu adres alınmış, başka bir adres dene.': 'This address is taken, try another one.',
      'Bu adres kullanılamıyor, başka bir adres dene.': 'This address can’t be used, try another one.',
      'Vitrin bulunamadı': 'Showcase not found',
      'Bu vitrin yok ya da sahibi tarafından yayından kaldırılmış.': 'This showcase doesn’t exist or its owner has taken it offline.',
      'Kart aramaya git': 'Go to card search',
      'Toplam değer': 'Total value',
      'Aradığı kart': 'Looking for',
      'Vitrini paylaş': 'Share showcase',
      'Bağlantı kopyalandı': 'Link copied',
      'Koleksiyon': 'Collection',
      'Bu vitrinde henüz kart yok.': 'No cards in this showcase yet.',
      'Aradığım kartlar': 'Cards I’m looking for',
      'Kendi vitrinini oluştur': 'Create your own showcase',
      'Koleksiyonunu ücretsiz takip et, istersen bir bağlantıyla paylaş.': 'Track your collection for free and share it with a link if you like.',
      'Ücretsiz başla': 'Start for free',
      'Değerler TCGplayer piyasa fiyatlarından ve eBay satışlarından hesaplanan tahminlerdir. Kartların sahipliği ve durumu Holotique tarafından doğrulanmaz. Yatırım tavsiyesi değildir.': 'Values are estimates based on TCGplayer market prices and eBay sales. Holotique does not verify ownership or condition of the cards. Not investment advice.',
      'Vitrin (isteğe bağlı)': 'Showcase (optional)',
      'Vitrinini açarsan, seçtiğin kartlar bir bağlantı üzerinden herkese görünür: kart adı, set, derece, adet ve (izin verirsen) güncel piyasa değeri. Alış fiyatların, alış tarihlerin, sertifika numaraların, hedef fiyatların ve e-posta adresin vitrinde yer almaz. Vitrini istediğin an kapatabilirsin; bağlantı hemen çalışmaz olur.': 'If you turn on your showcase, the cards you choose are visible to anyone with the link: card name, set, grade, quantity and (if you allow it) current market value. Your purchase prices, purchase dates, cert numbers, target prices and email address are never included. You can turn the showcase off at any time; the link stops working immediately.',
      'Veriler okunamadı': 'Could not load data', 'Tümü ▾': 'All ▾',

      // gizlilik sayfası
      'Gizlilik bildirimi': 'Privacy notice', 'Son güncelleme: 19 Ekim 2026': 'Last updated: October 19, 2026',
      'Portföy bilgilerin': 'Your portfolio data',
      'Hesabına eklediğin kartlar, alış fiyatların, alış tarihlerin ve sertifika numaraların yalnızca sana görünür. Bu kural veritabanı düzeyinde uygulanır: başka hiçbir kullanıcı bu bilgilere erişemez.':
        'The cards you add, your purchase prices, purchase dates and certificate numbers are visible only to you. This rule is enforced at the database level: no other user can access this information.',
      'Site yöneticisinin görebildikleri': 'What the site administrator can see',
      'Siteyi geliştirmek için yönetici şunları görebilir: toplu sayılar (örneğin "bir kart kaç portföyde var", portföy büyüklüklerinin dağılımı) ve':
        'To improve the site, the administrator can see: aggregate numbers (e.g. "how many portfolios hold a card", the distribution of portfolio sizes) and',
      'kimliğinden arındırılmış portföy içerikleri': 'de-identified portfolio contents',
      '— yani rastgele bir kodla gösterilen kart listesi, dereceler, adetler ve güncel piyasa değeri. Bu görünümde e-posta adresin, alış fiyatların, alış tarihlerin ve sertifika numaraların':
        '— a card list shown under a random code, with grades, quantities and current market value. This view does',
      'yer almaz': 'not include',
      've kodlar e-posta adresiyle eşleştirilemez. Yönetici, hesap yönetimi için kayıtlı e-posta adreslerini, kayıt ve son giriş tarihlerini ayrıca görebilir; bu liste portföy bilgisi içermez.':
        'your email address, purchase prices, purchase dates or certificate numbers, and the codes cannot be matched to an email address. For account management the administrator can separately see registered email addresses with sign-up and last sign-in dates; that list contains no portfolio information.',
      'Anonim kullanım istatistikleri': 'Anonymous usage statistics',
      'Siteyi geliştirmek için şunları sayıyoruz: arama kutusuna yazılan kelimeler ve kaç sonuç bulunduğu, detayı açılan kartlar ve zamanı. Bu kayıtlar seni tanımlayan hiçbir bilgiyle (hesap, e-posta, IP adresi) ilişkilendirilmez. Amaç, katalogda eksik kartları bulmak ve ilgi gören kartları öne çıkarmaktır.':
        'To improve the site we count: words typed into the search box and how many results were found, which cards were opened, and when. These records are never linked to anything that identifies you (account, email, IP address). The goal is to find cards missing from the catalog and to highlight cards people are interested in.',
      'Hesap bilgileri': 'Account details',
      'Giriş için e-posta adresin ve şifren (şifrelenmiş olarak) Supabase altyapısında saklanır. E-posta adresin yalnızca hesap onayı ve şifre sıfırlama için kullanılır; üçüncü taraflarla paylaşılmaz, pazarlama için kullanılmaz.':
        'Your email address and password (encrypted) are stored on Supabase infrastructure for sign-in. Your email is used only for account confirmation and password resets; it is not shared with third parties or used for marketing.',
      'Tarayıcında saklananlar': 'Stored in your browser',
      'Seçtiğin para birimi, son aramaların ve son baktığın kartlar yalnızca kendi tarayıcında saklanır; sunucuya gönderilmez. Tarayıcı verilerini sildiğinde kaybolur.':
        'Your chosen currency and language, recent searches and recently viewed cards are stored only in your own browser and never sent to our server. They disappear when you clear your browser data.',
      'Veri kaynakları': 'Data sources',
      'Fiyatlar TCGplayer (TCGCSV aracılığıyla) ve eBay satışlarından (PokemonPriceTracker) gelir. Gösterilen fiyatlar bilgi amaçlıdır, yatırım tavsiyesi değildir.':
        'Prices come from TCGplayer (via TCGCSV) and eBay sales (PokemonPriceTracker). Prices shown are for information only and are not investment advice.',
      'Hesabını silmek': 'Deleting your account',
      'Hesabının ve bütün portföy verilerinin silinmesini istersen':'If you want your account and all portfolio data deleted, write to',
      'adresine yazman yeterli; kalıcı olarak sileriz.':'and we will delete it permanently.',
      'İletişim':'Contact','Soru, öneri ve talepler için:':'Questions, suggestions and requests:'
    },
    // Dinamik metinler: sırayla uygulanır (yalnızca Türkçe kalıplar eşleşir)
    patterns: [
      [/^(.+) fiyat geçmişi, USD$/, function (m, a) { return (D.exact[a] || a) + ' price history, USD'; }],
      [/^(.+) değeri, USD$/, function (m, a) { return (D.exact[a] || a) + ' value, USD'; }],
      [/^(.+) · değer$/, '$1 · value'],
      [/^Kartlarım · /, 'My cards · '],
      [/^(\S+) sertifika no$/, '$1 cert no'],
      [/^Klasör: /, 'Folder: '],
      [/^Satılık · /, 'For sale · '],
      [/^Satılık kartlarım · /, 'My cards for sale · '],
      [/^Piyasa ≈ /, 'Market ≈ '],
      [/ · piyasa fiyatında$/, ' · at market price'],
      [/ · %(\d+) altında$/, ' · $1% below'],
      [/ · %(\d+) üstünde$/, ' · $1% above'],
      [/ · Satıcıya yazma tıklaması: /, ' · Contact clicks: '],
      [/^İstek listesi · /, 'Wishlist · '],
      [/^(\d+) kart hedef fiyatına indi\.$/, '$1 cards reached their target price.'],
      [/^hedef /, 'target '],
      [/^Eklendiğinde: (.+) · şimdi: /, 'When added: $1 · now: '],
      [/^Görüntülenme: /, 'Views: '],
      [/^Vitrin · @/, 'Showcase · @'],
      [/^(.+) fiyat geçmişi, USD$/, function (m, a) { return (D.exact[a] || a) + ' price history, USD'; }],
      [/^Set: /, 'Set: '],
      [/^Son baktıkların · /, 'Recently viewed · '],
      [/^En değerli kartlar · /, 'Most valuable cards · '],
      [/ aramasını sil$/, ' — remove search'],
      [/^(\S+) içinde$/, 'in $1'],
      [/^Ham (\d+%)$/, 'Raw $1'],
      [/^Ham · /, 'Raw · '],
      [/^Ham \(raw\) · /, 'Raw · '],
      [/^Diğer dereceli · /, 'Other graded · '],
      [/^Tümü · /, 'All · '],
      [/^Toplam: /, 'Total: '],
      [/^Kur etkisi · /, 'FX effect · '],
      [/^alıştan bu yana USD\//, 'since purchase USD/'],
      [/^maliyet /, 'cost '],
      [/\b(7|30|90)G\b/g, '$1D'],
      [/ kart fiyat bekliyor/, ' cards awaiting price'],
      [/(\d+) günlük kayıt · noktanın üzerine gel: o günün kuruyla (\w+) karşılığı/, '$1 days recorded · hover a point for the $2 value at that day’s rate'],
      [/^(yüksek|orta|düşük) güven/, function (m, c) { return { 'yüksek': 'high', 'orta': 'medium', 'düşük': 'low' }[c] + ' confidence'; }],
      [/^([\d.,]+) kart · ilk ([\d.,]+) gösteriliyor$/, '$1 cards · showing first $2'],
      [/^([\d.,]+) kart · (.+) · ilk ([\d.,]+) gösteriliyor$/, '$1 cards · $2 · showing first $3'],
      [/^([\d.,]+) kart · /, '$1 cards · '],
      [/^([\d.,]+) kart$/, '$1 cards'],
      [/ kart$/, ' cards'],
      [/^Fiyatlar (\d)/, 'Prices $1'],
      [/^\+([\d.,]+) kart daha/, '+$1 more cards'],
      [/([\d.,]+) kart seçili/, '$1 cards selected'],
      [/ · ([\d.,]+) görünüyor/, ' · $1 shown'],
      [/^(\d+) kartı içe aktar$/, 'Import $1 cards'],
      [/^(\d+) kart bulundu · toplam maliyet /, '$1 cards found · total cost '],
      [/ · (\d+) kart zaten portföyünde \(PSA numarasına göre\), atlanacak/, ' · $1 already in your portfolio (by PSA number), will be skipped'],
      [/Satır (\d+): alış fiyatı yok, 0 kabul edildi\./g, 'Row $1: no purchase price, assumed 0.'],
      [/Satır (\d+): "(.+?)" derecesi için fiyat yok\./g, 'Row $1: no price for grade "$2".'],
      [/\(\+(\d+) uyarı\)/, '(+$1 warnings)'],
      [/^Aktarılamadı: /, 'Import failed: '], [/^Kaydedilemedi: /, 'Could not save: '], [/^Dosya okunamadı: /, 'Could not read file: '],
      [/^Eşleşme: (.+)\. Yanlışsa Düzenle ile set adını ya da numarayı düzelt; kart yeniden eşleştirilir\.$/, 'Match: $1. If wrong, use Edit to fix the set name or number; the card will be re-matched.'],
      [/^PSA kaydında derece (.+) görünüyor, portföyde (.+) girilmiş\. Düzenle ile kontrol et\.$/, 'The PSA record shows grade $1, but $2 was entered in your portfolio. Check it with Edit.'],
      [/^Fiyat kaynağı (.+) satışlarını (.+) ayrımı yapmadan veriyor\. Gösterilen değer yaklaşıktır; gerçek değer genellikle daha yüksektir\.$/, 'The price source reports $1 sales without separating $2. The value shown is approximate; the real value is usually higher.'],
      [/^(.+) satışları fiyat kaynağımızda ayrı tutulmuyor; (.+) satışlarının ortalaması gösteriliyor\. (.+) kartlar genellikle bunun belirgin üstünde işlem görür, bu yüzden değer temkinli tarafta kalır\.$/, '$1 sales are not tracked separately by our price source; the average of $2 sales is shown. $3 cards usually trade well above this, so the value is conservative.'],
      // eşleştirme notları (fiyat görevinden gelir)
      [/ · set adı tutmadı, kontrol et/, ' · set name didn’t match, please check'],
      [/ · birden fazla aday vardı, kontrol et/, ' · multiple candidates, please check'],
      [/ · birden fazla aday vardı/, ' · multiple candidates'],
      [/ · PSA kaydıyla eşleşti/, ' · matched via PSA record'],
      [/ · yalnızca ham fiyat \(TCGplayer\)/, ' · raw price only (TCGplayer)'],
      [/^Kart bulunamadı\. Set adını ve numarayı kontrol et\./, 'Card not found. Check the set name and number.'],
      [/ Benzer: /, ' Similar: '],
      [/^Katalogda bulunamadı\. Kart adını ve numarasını \(ör\. OP05-119\) kontrol et\.$/, 'Not found in the catalog. Check the card name and number (e.g. OP05-119).'],
      [/^Katalogda bu numarayla kart bulunamadı\. Numarayı kontrol et\.$/, 'No card with this number in the catalog. Check the number.'],
      [/ için PSA fiyat kaynağı henüz bağlı değil\.$/, ': no PSA price source connected yet.'],
      [/([\d.,]+) satış(?![a-zçğıöşü])/g, '$1 sales'],
      // tarih: 19 Eki 2026 → Oct 19, 2026
      [/(\d{1,2}) (Oca|Şub|Mar|Nis|May|Haz|Tem|Ağu|Eyl|Eki|Kas|Ara)( (\d{4}))?\b/g, function (m, d, mon, y, yy) {
        var en = MONTHS_EN[MONTHS_TR.indexOf(mon)]; return en + ' ' + d + (yy ? ', ' + yy : ''); }]
    ]
  };

  var D = DICT[LANG];
  function tr(s) {
    if (!D || !s) return s;
    var lead = s.match(/^\s*/)[0], tail = s.match(/\s*$/)[0], t = s.trim();
    if (!t) return s;
    var hit = D.exact[t];
    if (hit != null) return lead + hit + tail;
    var out = t;
    for (var i = 0; i < D.patterns.length; i++) out = out.replace(D.patterns[i][0], D.patterns[i][1]);
    return out === t ? s : lead + out + tail;
  }
  window.HQ_T = tr;

  var ATTRS = ['placeholder', 'title', 'aria-label'];
  function walk(root) {
    if (!D || !root) return;
    if (root.nodeType === 3) { var v = tr(root.nodeValue); if (v !== root.nodeValue) root.nodeValue = v; return; }
    if (root.nodeType !== 1 || /^(SCRIPT|STYLE)$/.test(root.tagName)) return;
    if (root.hasAttribute && root.hasAttribute('data-no-i18n')) return;
    ATTRS.forEach(function (a) { var v = root.getAttribute && root.getAttribute(a); if (v) { var n = tr(v); if (n !== v) root.setAttribute(a, n); } });
    if (root.tagName === 'TEXTAREA') return;  // kullanıcının yazdığı metne dokunma
    for (var c = root.firstChild; c; c = c.nextSibling) walk(c);
  }

  function picker() {
    var host = document.querySelector('.top .wrap');
    if (!host || host.querySelector('.lang')) return;
    var box = document.createElement('div'); box.className = 'seg lang'; box.setAttribute('role', 'group'); box.setAttribute('aria-label', LANG === 'tr' ? 'Dil' : 'Language');
    box.setAttribute('data-no-i18n', '');
    LANGS.forEach(function (l) {
      var b = document.createElement('button'); b.type = 'button'; b.textContent = l[1]; b.title = l[2];
      b.setAttribute('aria-pressed', String(l[0] === LANG));
      b.addEventListener('click', function () { if (l[0] === LANG) return; store.set('hq-lang', l[0]); location.reload(); });
      box.appendChild(b);
    });
    host.appendChild(box);
  }

  function start() {
    picker();
    if (!D) return;
    document.title = tr(document.title);
    walk(document.body);
    new MutationObserver(function (list) {
      list.forEach(function (m) {
        if (m.type === 'characterData') walk(m.target);
        else if (m.type === 'attributes') walk(m.target);
        else m.addedNodes.forEach(walk);
      });
      var t = tr(document.title); if (t !== document.title) document.title = t;
    }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
