"""
Static UI translations  -  WhatWay site-wide labels (no LLM).
"""

from __future__ import annotations

import re
from typing import Dict, List

LANGUAGES: Dict[str, str] = {
    "en": "English",
    "es": "Español",
    "ar": "العربية",
    "fr": "Français",
    "pl": "Polski",
    "zh": "中文",
    "ur": "اردو",
    "hi": "हिन्दी",
    "uk": "Українська",
    "sw": "Kiswahili",
}

NAME_TO_CODE = {
    "Auto-detect": "auto",
    "English": "en",
    "Spanish": "es",
    "Arabic": "ar",
    "French": "fr",
    "Polish": "pl",
    "Mandarin": "zh",
    "Chinese": "zh",
    "Urdu": "ur",
    "Hindi": "hi",
    "Ukrainian": "uk",
    "Swahili": "sw",
}

CODE_TO_NAME = {v: k for k, v in NAME_TO_CODE.items() if k not in ("Auto-detect", "Chinese")}

_EN = {
    "brand": "WhatWay",
    "tagline": "Care & community help  -  Chicago first.",
    "bot_name": "Pip",
    "bot_hello": "Hey! I'm Pip.",
    "ask_prefix": "Ask about ",
    "ask_placeholder": "Type your message here…",
    "category_label": "What do you need?",
    "healthcare": "Healthcare",
    "education": "Education",
    "resettlement": "Legal & Shelter",
    "language_label": "Language",
    "ai_online": "AI online",
    "ai_offline": "AI offline  -  start Ollama (`ollama serve`)",
    "ollama_hint": "Start Ollama: `ollama serve`",
    "pinned": "Saved",
    "pinned_empty": "Nothing saved yet",
    "filters": "Filters",
    "reset": "Reset chat",
    "scroll_latest": "Scroll to latest",
    "whatsapp_hint": "Prefer texting? WhatsApp is in beta.",
    "no_results": "I couldn't find a match. Try another ZIP, neighborhood, or service.",
    "found_n": "Here are {n} options for you:",
    "call": "Call",
    "more_hint": "Type more for more results.",
    "more_caption": "Want more options? Type more.",
    "forms_users": "For users",
    "forms_clinics": "For clinics",
    "forms_users_btn": "Report incorrect info",
    "forms_clinics_btn": "Request a listing update",
    "forms_users_cap": "Anyone can report wrong hours, phones, languages, or closures.",
    "forms_clinics_cap": "Clinic staff  -  update hours, services, eligibility, or contact info.",
    "forms_section": "Improve listings",
    "filter_zip": "ZIP",
    "filter_lang": "Language spoken",
    "filter_service": "Service",
    "filter_day": "Day",
    "filter_all": "All",
    "filter_state": "State",
    "filter_state_placeholder": "Select a state",
    "filter_zip_locked": "Choose a state to unlock ZIP codes",
    "view_details": "Details & comments",
    "details_short": "Details",
    "comments_short": "Comments",
    "pin": "Pin",
    "unpin": "Unpin",
    "auth": "Account",
    "login": "Login",
    "register": "Register",
    "logout": "Logout",
    "username": "Username",
    "username_email": "Username / email",
    "email": "Email",
    "password": "Password",
    "create_account": "Create account",
    "fill_fields": "Please fill in all fields",
    "password_short": "Password must be 6+ characters",
    "account_created": "Account created! Please login.",
    "directions": "Get directions",
    "where": "Where",
    "phone_label": "Call",
    "website_label": "Website",
    "they_speak": "Languages",
    "they_offer": "Services",
    "hours_label": "Hours",
    "opens": "Opens {when}",
    "comments_n": "{n} comments",
    "tip_search": "Tip: include a ZIP or service in your search (e.g. dental 60629).",
    "tip_search_days": "Tip: include ZIP, service, or day (e.g. dental 60629, ESL monday).",
    "tip_neighborhood": "You can search by neighborhood (e.g. Pilsen, Rogers Park).",
    "status_section": "Status",
    "nav_section": "Navigate",
    "recent": "Recent",
    "map_short": "Map",
    "view_cards": "Cards",
    "open_now_chip": "Open now",
    "verified": "Verified {when}",
    "results_intro": "Here are a few **{category}** options for **{q}**{where}. Tap a site or map when you’re ready.",
    "results_near": " near **{z}**",
    "results_for_svc": " for **{svc}**",
    "voice_fallback_note": "No voice for this language on your device yet  -  Pip will speak in English for now.",
}

ASK_PHRASES: Dict[str, List[str]] = {
    "en": ["dental care", "ESL nearby", "legal aid", "shelter tonight", "a clinic near you"],
    "es": ["cuidado dental", "clases de ESL", "ayuda legal", "refugio hoy", "una clínica cerca"],
    "ar": ["رعاية أسنان", "دروس إنجليزية", "مساعدة قانونية", "مأوى الليلة", "عيادة قريبة"],
    "fr": ["soins dentaires", "cours d'anglais", "aide juridique", "abri ce soir", "une clinique proche"],
    "pl": ["dentysta", "kurs angielskiego", "pomoc prawna", "schronisko dziś", "klinika w pobliżu"],
    "zh": ["牙科", "英语课", "法律援助", "今晚收容", "附近诊所"],
    "ur": ["دانتوں کی دیکھ بھال", "انگریزی کلاس", "قانونی مدد", "آج رات پناہ", "قریبی کلینک"],
    "hi": ["दंत चिकित्सा", "अंग्रेज़ी कक्षा", "कानूनी मदद", "आज रात आश्रय", "पास का क्लिनिक"],
    "uk": ["стоматологія", "англійська", "юридична допомога", "притулок сьогодні", "клініка поруч"],
    "sw": ["meno", "kiingereza", "msaada wa kisheria", "hifadhi leo", "kliniki karibu"],
}


_ES = {
    **_EN,
    "tagline": "Cuidado y ayuda comunitaria  -  primero Chicago.",
    "bot_hello": "¡Hola! Soy Pip.",
    "ask_prefix": "Pregunta por ",
    "ask_placeholder": "Escribe tu mensaje aquí…",
    "category_label": "¿Qué necesitas?",
    "healthcare": "Salud",
    "education": "Educación",
    "resettlement": "Legal y Refugio",
    "language_label": "Idioma",
    "ai_online": "IA activa",
    "ai_offline": "IA desactivada  -  inicia Ollama",
    "ollama_hint": "Inicia Ollama: `ollama serve`",
    "pinned": "Guardados",
    "pinned_empty": "Nada guardado aún",
    "filters": "Filtros",
    "reset": "Reiniciar chat",
    "scroll_latest": "Ir al final",
    "whatsapp_hint": "¿Prefieres WhatsApp? Está en prueba.",
    "no_results": "No encontré resultados. Prueba otro ZIP o servicio.",
    "found_n": "Aquí tienes {n} opciones:",
    "call": "Llamar",
    "more_hint": "Escribe more para ver más.",
    "more_caption": "¿Más opciones? Escribe more.",
    "forms_users": "Para usuarios",
    "forms_clinics": "Para clínicas",
    "forms_users_btn": "Reportar info incorrecta",
    "forms_clinics_btn": "Solicitar actualización",
    "forms_users_cap": "Cualquiera puede reportar horarios, teléfonos o idiomas incorrectos.",
    "forms_clinics_cap": "Personal de la clínica  -  actualizar horarios, servicios o contacto.",
    "forms_section": "Mejorar listados",
    "filter_zip": "ZIP",
    "filter_lang": "Idioma hablado",
    "filter_service": "Servicio",
    "filter_day": "Día",
    "filter_all": "Todos",
    "filter_state": "Estado",
    "filter_state_placeholder": "Elige un estado",
    "filter_zip_locked": "Elige un estado para ver códigos ZIP",
    "view_details": "Detalles y comentarios",
    "details_short": "Detalles",
    "comments_short": "Comentarios",
    "pin": "Fijar",
    "unpin": "Quitar",
    "auth": "Cuenta",
    "login": "Entrar",
    "register": "Registrarse",
    "logout": "Salir",
    "username": "Usuario",
    "username_email": "Usuario / correo",
    "email": "Correo",
    "password": "Contraseña",
    "create_account": "Crear cuenta",
    "fill_fields": "Completa todos los campos",
    "password_short": "La contraseña debe tener 6+ caracteres",
    "account_created": "¡Cuenta creada! Inicia sesión.",
    "directions": "Cómo llegar",
    "where": "Dónde",
    "phone_label": "Llamar",
    "website_label": "Sitio web",
    "they_speak": "Idiomas",
    "they_offer": "Servicios",
    "hours_label": "Horario",
    "opens": "Abre {when}",
    "comments_n": "{n} comentarios",
    "tip_search": "Consejo: incluye ZIP o servicio (ej. dental 60629).",
    "tip_search_days": "Consejo: incluye ZIP, servicio o día (ej. dental 60629, ESL monday).",
    "tip_neighborhood": "También puedes buscar por barrio (ej. Pilsen, Rogers Park).",
    "status_section": "Estado",
    "nav_section": "Navegar",
    "recent": "Recientes",
}

_AR = {
    **_EN,
    "tagline": "رعاية وموارد  -  شيكاغو أولاً.",
    "bot_hello": "مرحباً! أنا بيب.",
    "ask_prefix": "اسأل عن ",
    "ask_placeholder": "اكتب رسالتك هنا…",
    "category_label": "ماذا تحتاج؟",
    "healthcare": "الرعاية الصحية",
    "education": "التعليم",
    "resettlement": "قانوني ومأوى",
    "language_label": "اللغة",
    "ai_online": "متصل",
    "ai_offline": "غير متصل  -  شغّل Ollama",
    "ollama_hint": "شغّل Ollama: `ollama serve`",
    "pinned": "المحفوظات",
    "pinned_empty": "لا شيء محفوظ",
    "filters": "تصفية",
    "reset": "إعادة تعيين",
    "whatsapp_hint": "تفضل واتساب؟ الميزة قيد التجربة.",
    "forms_users": "للمستخدمين",
    "forms_clinics": "للعيادات",
    "forms_users_btn": "الإبلاغ عن معلومات خاطئة",
    "forms_clinics_btn": "طلب تحديث القائمة",
    "forms_section": "تحسين القوائم",
    "view_details": "التفاصيل والتعليقات",
    "details_short": "التفاصيل",
    "pin": "تثبيت",
    "unpin": "إلغاء",
    "auth": "الحساب",
    "login": "دخول",
    "register": "تسجيل",
    "logout": "خروج",
    "directions": "الاتجاهات",
    "where": "الموقع",
    "they_speak": "اللغات",
    "they_offer": "الخدمات",
    "hours_label": "الساعات",
    "tip_search": "نصيحة: أضف الرمز البريدي أو الخدمة (مثال dental 60629).",
    "tip_neighborhood": "يمكنك البحث بالحي (مثل Pilsen).",
    "status_section": "الحالة",
    "recent": "الأخيرة",
}

_FR = {
    **_EN,
    "tagline": "Soins et aide  -  Chicago d'abord.",
    "bot_hello": "Salut ! Je suis Pip.",
    "ask_prefix": "Demandez ",
    "ask_placeholder": "Écrivez votre message ici…",
    "category_label": "De quoi avez-vous besoin ?",
    "healthcare": "Santé",
    "education": "Éducation",
    "resettlement": "Juridique & Hébergement",
    "language_label": "Langue",
    "ai_online": "IA en ligne",
    "ai_offline": "IA hors ligne  -  démarrez Ollama",
    "ollama_hint": "Démarrez Ollama : `ollama serve`",
    "pinned": "Enregistrés",
    "pinned_empty": "Rien d'enregistré",
    "filters": "Filtres",
    "reset": "Réinitialiser",
    "whatsapp_hint": "Vous préférez WhatsApp ? Bêta disponible.",
    "forms_users": "Pour les usagers",
    "forms_clinics": "Pour les cliniques",
    "forms_users_btn": "Signaler une erreur",
    "forms_clinics_btn": "Demander une mise à jour",
    "forms_section": "Améliorer les fiches",
    "view_details": "Détails & commentaires",
    "details_short": "Détails",
    "pin": "Épingler",
    "unpin": "Retirer",
    "auth": "Compte",
    "login": "Connexion",
    "register": "S'inscrire",
    "logout": "Déconnexion",
    "directions": "Itinéraire",
    "where": "Adresse",
    "they_speak": "Langues",
    "they_offer": "Services",
    "hours_label": "Horaires",
    "tip_search": "Astuce : ajoutez un ZIP ou un service (ex. dental 60629).",
    "tip_neighborhood": "Vous pouvez chercher par quartier (ex. Pilsen).",
    "status_section": "État",
    "recent": "Récents",
}

_PL = {
    **_EN,
    "tagline": "Opieka i pomoc  -  najpierw Chicago.",
    "bot_hello": "Cześć! Jestem Pip.",
    "ask_prefix": "Zapytaj o ",
    "ask_placeholder": "Napisz wiadomość…",
    "category_label": "Czego potrzebujesz?",
    "healthcare": "Zdrowie",
    "education": "Edukacja",
    "resettlement": "Prawo i schronienie",
    "language_label": "Język",
    "ai_online": "AI online",
    "ai_offline": "AI offline  -  uruchom Ollama",
    "pinned": "Zapisane",
    "pinned_empty": "Nic jeszcze nie zapisano",
    "filters": "Filtry",
    "reset": "Resetuj czat",
    "whatsapp_hint": "Wolisz WhatsApp? Wersja beta.",
    "no_results": "Brak wyników. Spróbuj innego ZIP lub usługi.",
    "found_n": "Oto {n} opcji:",
    "forms_section": "Ulepsz listy",
    "forms_users": "Dla użytkowników",
    "forms_clinics": "Dla klinik",
    "forms_users_btn": "Zgłoś błąd",
    "forms_clinics_btn": "Poproś o aktualizację",
    "forms_users_cap": "Zgłoś złe godziny, telefony lub języki.",
    "forms_clinics_cap": "Personel klinik  -  aktualizuj dane.",
    "view_details": "Szczegóły i komentarze",
    "details_short": "Szczegóły",
    "pin": "Zapisz",
    "unpin": "Usuń",
    "auth": "Konto",
    "login": "Zaloguj",
    "register": "Zarejestruj",
    "logout": "Wyloguj",
    "directions": "Wskazówki",
    "where": "Adres",
    "phone_label": "Zadzwoń",
    "website_label": "Strona",
    "they_speak": "Języki",
    "they_offer": "Usługi",
    "hours_label": "Godziny",
    "opens": "Otwiera {when}",
    "comments_n": "{n} komentarzy",
    "tip_search": "Wskazówka: podaj ZIP lub usługę (np. dental 60629).",
    "tip_neighborhood": "Możesz szukać po dzielnicy (np. Pilsen).",
    "recent": "Ostatnie",
    "filter_zip": "ZIP",
    "filter_lang": "Język",
    "filter_service": "Usługa",
    "filter_day": "Dzień",
    "filter_all": "Wszystkie",
    "more_caption": "Więcej opcji? Napisz more.",
}

_ZH = {
    **_EN,
    "tagline": "关怀与社区帮助  -  芝加哥优先。",
    "bot_hello": "你好！我是 Pip。",
    "ask_prefix": "询问 ",
    "ask_placeholder": "在此输入消息…",
    "category_label": "您需要什么？",
    "healthcare": "医疗",
    "education": "教育",
    "resettlement": "法律与收容",
    "language_label": "语言",
    "ai_online": "AI 在线",
    "ai_offline": "AI 离线  -  请启动 Ollama",
    "pinned": "已保存",
    "pinned_empty": "暂无保存",
    "filters": "筛选",
    "reset": "重置对话",
    "whatsapp_hint": "想用 WhatsApp？测试中。",
    "no_results": "未找到结果。请换个邮编或服务再试。",
    "found_n": "为您找到 {n} 个选项：",
    "forms_section": "完善信息",
    "forms_users": "用户",
    "forms_clinics": "诊所",
    "forms_users_btn": "报告错误信息",
    "forms_clinics_btn": "申请更新",
    "forms_users_cap": "可报告错误的时间、电话或语言。",
    "forms_clinics_cap": "诊所工作人员可更新资料。",
    "view_details": "详情与评论",
    "details_short": "详情",
    "pin": "收藏",
    "unpin": "取消",
    "auth": "账户",
    "login": "登录",
    "register": "注册",
    "logout": "退出",
    "directions": "导航",
    "where": "地址",
    "phone_label": "电话",
    "website_label": "网站",
    "they_speak": "语言",
    "they_offer": "服务",
    "hours_label": "营业时间",
    "opens": "{when} 开放",
    "comments_n": "{n} 条评论",
    "tip_search": "提示：请包含邮编或服务（如 dental 60629）。",
    "tip_neighborhood": "也可按社区搜索（如 Pilsen）。",
    "recent": "最近",
    "filter_all": "全部",
    "more_caption": "需要更多？输入 more。",
}

_UR = {
    **_EN,
    "tagline": "نگہداشت اور مدد  -  پہلے شکاگو۔",
    "bot_hello": "ہیلو! میں پِپ ہوں۔",
    "ask_prefix": "پوچھیں ",
    "ask_placeholder": "اپنا پیغام لکھیں…",
    "category_label": "آپ کو کیا چاہیے؟",
    "healthcare": "صحت",
    "education": "تعلیم",
    "resettlement": "قانونی و پناہ",
    "language_label": "زبان",
    "ai_online": "AI آن لائن",
    "ai_offline": "AI آف لائن  -  Ollama چلائیں",
    "pinned": "محفوظ",
    "pinned_empty": "ابھی کچھ محفوظ نہیں",
    "filters": "فلٹر",
    "reset": "چیٹ ری سیٹ",
    "whatsapp_hint": "WhatsApp پسند ہے؟ بیٹا دستیاب۔",
    "no_results": "کوئی نتیجہ نہیں۔ دوسرا ZIP یا سروس آزمائیں۔",
    "found_n": "یہ {n} اختیارات ہیں:",
    "forms_section": "فہرست بہتر بنائیں",
    "forms_users": "صارفین کے لیے",
    "forms_clinics": "کلینکس کے لیے",
    "forms_users_btn": "غلط معلومات رپورٹ کریں",
    "forms_clinics_btn": "اپ ڈیٹ کی درخواست",
    "view_details": "تفصیلات اور تبصرے",
    "details_short": "تفصیلات",
    "pin": "محفوظ کریں",
    "unpin": "ہٹائیں",
    "auth": "اکاؤنٹ",
    "login": "لاگ ان",
    "register": "رجسٹر",
    "logout": "لاگ آؤٹ",
    "directions": "راستہ",
    "where": "پتہ",
    "phone_label": "کال",
    "website_label": "ویب سائٹ",
    "they_speak": "زبانیں",
    "they_offer": "خدمات",
    "hours_label": "اوقات",
    "opens": "{when} کھلتا ہے",
    "comments_n": "{n} تبصرے",
    "tip_search": "ٹپ: ZIP یا سروس شامل کریں (جیسے dental 60629)۔",
    "tip_neighborhood": "آپ محلے سے بھی تلاش کر سکتے ہیں (جیسے Pilsen)۔",
    "recent": "حالیہ",
    "filter_all": "سب",
    "more_caption": "مزید؟ more لکھیں۔",
}

_HI = {
    **_EN,
    "tagline": "देखभाल और सहायता  -  पहले शिकागो।",
    "bot_hello": "नमस्ते! मैं Pip हूँ।",
    "ask_prefix": "पूछें ",
    "ask_placeholder": "यहाँ संदेश लिखें…",
    "category_label": "आपको क्या चाहिए?",
    "healthcare": "स्वास्थ्य",
    "education": "शिक्षा",
    "resettlement": "कानूनी और आश्रय",
    "language_label": "भाषा",
    "ai_online": "AI ऑनलाइन",
    "ai_offline": "AI ऑफ़लाइन  -  Ollama शुरू करें",
    "pinned": "सहेजे गए",
    "pinned_empty": "अभी कुछ नहीं बचाया",
    "filters": "फ़िल्टर",
    "reset": "चैट रीसेट",
    "whatsapp_hint": "WhatsApp पसंद है? बीटा उपलब्ध।",
    "no_results": "कोई परिणाम नहीं। दूसरा ZIP या सेवा आज़माएँ।",
    "found_n": "यहाँ {n} विकल्प हैं:",
    "forms_section": "सूची सुधारें",
    "forms_users": "उपयोगकर्ताओं के लिए",
    "forms_clinics": "क्लिनिक के लिए",
    "forms_users_btn": "गलत जानकारी रिपोर्ट करें",
    "forms_clinics_btn": "अपडेट का अनुरोध",
    "view_details": "विवरण और टिप्पणियाँ",
    "details_short": "विवरण",
    "pin": "सेव",
    "unpin": "हटाएँ",
    "auth": "खाता",
    "login": "लॉगिन",
    "register": "रजिस्टर",
    "logout": "लॉगआउट",
    "directions": "दिशा",
    "where": "पता",
    "phone_label": "कॉल",
    "website_label": "वेबसाइट",
    "they_speak": "भाषाएँ",
    "they_offer": "सेवाएँ",
    "hours_label": "समय",
    "opens": "{when} खुलता है",
    "comments_n": "{n} टिप्पणियाँ",
    "tip_search": "सुझाव: ZIP या सेवा जोड़ें (जैसे dental 60629)।",
    "tip_neighborhood": "आप इलाके से भी खोज सकते हैं (जैसे Pilsen)।",
    "recent": "हाल ही में",
    "filter_all": "सभी",
    "more_caption": "और चाहिए? more लिखें।",
}

_UK = {
    **_EN,
    "tagline": "Допомога громаді  -  спочатку Чикаго.",
    "bot_hello": "Привіт! Я Pip.",
    "ask_prefix": "Запитайте про ",
    "ask_placeholder": "Напишіть повідомлення…",
    "category_label": "Що вам потрібно?",
    "healthcare": "Охорона здоров'я",
    "education": "Освіта",
    "resettlement": "Право і притулок",
    "language_label": "Мова",
    "ai_online": "ШІ онлайн",
    "ai_offline": "ШІ офлайн  -  запустіть Ollama",
    "pinned": "Збережене",
    "pinned_empty": "Ще нічого не збережено",
    "filters": "Фільтри",
    "reset": "Скинути чат",
    "whatsapp_hint": "Краще WhatsApp? Бета доступна.",
    "no_results": "Нічого не знайдено. Спробуйте інший ZIP або послугу.",
    "found_n": "Ось {n} варіантів:",
    "forms_section": "Покращити списки",
    "forms_users": "Для користувачів",
    "forms_clinics": "Для клінік",
    "forms_users_btn": "Повідомити про помилку",
    "forms_clinics_btn": "Запросити оновлення",
    "view_details": "Деталі та коментарі",
    "details_short": "Деталі",
    "pin": "Зберегти",
    "unpin": "Прибрати",
    "auth": "Обліковий запис",
    "login": "Увійти",
    "register": "Реєстрація",
    "logout": "Вийти",
    "directions": "Маршрут",
    "where": "Адреса",
    "phone_label": "Подзвонити",
    "website_label": "Сайт",
    "they_speak": "Мови",
    "they_offer": "Послуги",
    "hours_label": "Години",
    "opens": "Відчиняється {when}",
    "comments_n": "{n} коментарів",
    "tip_search": "Порада: додайте ZIP або послугу (напр. dental 60629).",
    "tip_neighborhood": "Можна шукати за районом (напр. Pilsen).",
    "recent": "Недавні",
    "filter_all": "Усі",
    "more_caption": "Більше? Напишіть more.",
}

_SW = {
    **_EN,
    "tagline": "Huduma na msaada  -  Chicago kwanza.",
    "bot_hello": "Habari! Mimi ni Pip.",
    "ask_prefix": "Uliza kuhusu ",
    "ask_placeholder": "Andika ujumbe hapa…",
    "category_label": "Unahitaji nini?",
    "healthcare": "Afya",
    "education": "Elimu",
    "resettlement": "Sheria na makazi",
    "language_label": "Lugha",
    "ai_online": "AI online",
    "ai_offline": "AI offline  -  anzisha Ollama",
    "pinned": "Imehifadhiwa",
    "pinned_empty": "Bado hakuna kilichohifadhiwa",
    "filters": "Vichujio",
    "reset": "Weka upya gumzo",
    "whatsapp_hint": "Unapendelea WhatsApp? Beta ipo.",
    "no_results": "Hakuna matokeo. Jaribu ZIP au huduma nyingine.",
    "found_n": "Hapa kuna chaguo {n}:",
    "forms_section": "Boresha orodha",
    "forms_users": "Kwa watumiaji",
    "forms_clinics": "Kwa kliniki",
    "forms_users_btn": "Ripoti taarifa potofu",
    "forms_clinics_btn": "Omba sasisho",
    "view_details": "Maelezo na maoni",
    "details_short": "Maelezo",
    "pin": "Hifadhi",
    "unpin": "Ondoa",
    "auth": "Akaunti",
    "login": "Ingia",
    "register": "Jisajili",
    "logout": "Toka",
    "directions": "Maelekezo",
    "where": "Anwani",
    "phone_label": "Piga simu",
    "website_label": "Tovuti",
    "they_speak": "Lugha",
    "they_offer": "Huduma",
    "hours_label": "Saa",
    "opens": "Inafungua {when}",
    "comments_n": "maoni {n}",
    "tip_search": "Kidokezo: ongeza ZIP au huduma (mf. dental 60629).",
    "tip_neighborhood": "Unaweza kutafuta kwa eneo (mf. Pilsen).",
    "recent": "Hivi karibuni",
    "filter_all": "Zote",
    "more_caption": "Zaidi? Andika more.",
}

STRINGS: Dict[str, Dict[str, str]] = {
    "en": dict(_EN),
    "es": _ES,
    "ar": _AR,
    "fr": _FR,
    "pl": _PL,
    "zh": _ZH,
    "ur": _UR,
    "hi": _HI,
    "uk": _UK,
    "sw": _SW,
}


def normalize_lang(code_or_name: str | None) -> str:
    if not code_or_name or code_or_name.lower() in ("auto", "auto-detect"):
        return "en"
    key = code_or_name.strip()
    if key.lower() in STRINGS:
        return key.lower()
    mapped = NAME_TO_CODE.get(key) or NAME_TO_CODE.get(key.title())
    if mapped and mapped != "auto":
        return mapped
    return "en"


def t(key: str, lang: str = "en", **kwargs) -> str:
    lang = normalize_lang(lang)
    table = STRINGS.get(lang) or STRINGS["en"]
    text = table.get(key) or STRINGS["en"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def ask_phrases(lang: str = "en") -> List[str]:
    lang = normalize_lang(lang)
    return ASK_PHRASES.get(lang) or ASK_PHRASES["en"]


def category_display(category: str, lang: str = "en") -> str:
    mapping = {
        "Healthcare": "healthcare",
        "Education": "education",
        "Resettlement / Legal / Shelter": "resettlement",
    }
    return t(mapping.get(category, "healthcare"), lang)


# --- Dynamic card / Pip localization (all UI languages) ---

_SPEECH_INTRO = {
    "es": "Aquí tienes algunas opciones de **{category}** para **{q}**{where}. Toca un sitio o el mapa cuando quieras.",
    "ar": "إليك بعض خيارات **{category}** لـ **{q}**{where}. اضغط على موقع أو الخريطة عندما تكون جاهزًا.",
    "fr": "Voici quelques options **{category}** pour **{q}**{where}. Touchez un lieu ou la carte quand vous voulez.",
    "pl": "Oto kilka opcji **{category}** dla **{q}**{where}. Dotknij miejsca lub mapy, gdy będziesz gotowy.",
    "zh": "这里有一些 **{category}** 选项，关于 **{q}**{where}。准备好后点选地点或地图。",
    "ur": "یہ رہیں چند **{category}** اختیارات **{q}** کے لیے{where}۔ تیار ہوں تو جگہ یا نقشہ تھپتھپائیں۔",
    "hi": "**{q}** के लिए कुछ **{category}** विकल्प यहाँ हैं{where}। तैयार हों तो स्थान या मानचित्र टैप करें।",
    "uk": "Ось кілька варіантів **{category}** для **{q}**{where}. Торкніться місця або карти, коли будете готові.",
    "sw": "Hapa kuna chaguo chache za **{category}** kwa **{q}**{where}. Gusa mahali au ramani ukiwa tayari.",
}
_NEAR = {
    "es": " cerca de **{z}**",
    "ar": " قرب **{z}**",
    "fr": " près de **{z}**",
    "pl": " w pobliżu **{z}**",
    "zh": "，靠近 **{z}**",
    "ur": " **{z}** کے قریب",
    "hi": " **{z}** के पास",
    "uk": " біля **{z}**",
    "sw": " karibu na **{z}**",
}
_FOR_SVC = {
    "es": " de **{svc}**",
    "ar": " لـ **{svc}**",
    "fr": "  -  **{svc}**",
    "pl": "  -  **{svc}**",
    "zh": "（**{svc}**）",
    "ur": "  -  **{svc}**",
    "hi": "  -  **{svc}**",
    "uk": "  -  **{svc}**",
    "sw": "  -  **{svc}**",
}
_MAP = {
    "es": "Mapa",
    "ar": "الخريطة",
    "fr": "Carte",
    "pl": "Mapa",
    "zh": "地图",
    "ur": "نقشہ",
    "hi": "मानचित्र",
    "uk": "Карта",
    "sw": "Ramani",
}
_COMMENTS = {
    "es": "Comentarios",
    "ar": "التعليقات",
    "fr": "Commentaires",
    "pl": "Komentarze",
    "zh": "评论",
    "ur": "تبصرے",
    "hi": "टिप्पणियाँ",
    "uk": "Коментарі",
    "sw": "Maoni",
}
_FILTER_STATE = {
    "es": "Estado",
    "ar": "الولاية",
    "fr": "État",
    "pl": "Stan",
    "zh": "州",
    "ur": "ریاست",
    "hi": "राज्य",
    "uk": "Штат",
    "sw": "Jimbo",
}
_FILTER_STATE_PLACEHOLDER = {
    "es": "Elige un estado",
    "ar": "اختر ولاية",
    "fr": "Choisir un État",
    "pl": "Wybierz stan",
    "zh": "选择州",
    "ur": "ریاست منتخب کریں",
    "hi": "राज्य चुनें",
    "uk": "Оберіть штат",
    "sw": "Chagua jimbo",
}
_FILTER_ZIP_LOCKED = {
    "es": "Elige un estado para ver códigos ZIP",
    "ar": "اختر ولاية لفتح الرموز البريدية",
    "fr": "Choisissez un État pour débloquer les ZIP",
    "pl": "Wybierz stan, aby odblokować kody ZIP",
    "zh": "先选择州以解锁邮政编码",
    "ur": "ZIP کے لیے ریاست منتخب کریں",
    "hi": "ZIP अनलॉक करने के लिए राज्य चुनें",
    "uk": "Оберіть штат, щоб відкрити ZIP",
    "sw": "Chagua jimbo ili kufungua ZIP",
}
_OPEN_NOW = {
    "es": "Abierto ahora",
    "ar": "مفتوح الآن",
    "fr": "Ouvert maintenant",
    "pl": "Otwarte teraz",
    "zh": "营业中",
    "ur": "ابھی کھلا",
    "hi": "अभी खुला",
    "uk": "Зараз відкрито",
    "sw": "Wazi sasa",
}

_VOICE_FALLBACK = {
    "es": "Aún no hay voz en este idioma en tu dispositivo  -  Pip hablará en inglés por ahora.",
    "ar": "لا يتوفر صوت لهذه اللغة على جهازك بعد  -  سيتحدث بيب بالإنجليزية مؤقتًا.",
    "fr": "Pas encore de voix pour cette langue sur votre appareil  -  Pip parlera en anglais pour l’instant.",
    "pl": "Brak głosu w tym języku na Twoim urządzeniu  -  Pip na razie mówi po angielsku.",
    "zh": "此设备暂无该语言的语音  -  Pip 暂时用英语朗读。",
    "ur": "آپ کے آلے پر ابھی اس زبان کی آواز نہیں  -  پپ فی الحال انگریزی میں بات کرے گا۔",
    "hi": "इस भाषा की आवाज़ आपके डिवाइस पर अभी नहीं है  -  Pip अभी अंग्रेज़ी में बोलेगा।",
    "uk": "Голосу цією мовою на пристрої ще немає  -  Pip поки говоритиме англійською.",
    "sw": "Sauti ya lugha hii haipo kwenye kifaa chako bado  -  Pip atasema Kiingereza kwa sasa.",
}

for _code in STRINGS:
    if _code == "en":
        continue
    if _code in _SPEECH_INTRO:
        STRINGS[_code]["results_intro"] = _SPEECH_INTRO[_code]
    if _code in _NEAR:
        STRINGS[_code]["results_near"] = _NEAR[_code]
    if _code in _FOR_SVC:
        STRINGS[_code]["results_for_svc"] = _FOR_SVC[_code]
    if _code in _MAP:
        STRINGS[_code]["map_short"] = _MAP[_code]
    if _code in _COMMENTS:
        STRINGS[_code]["comments_short"] = _COMMENTS[_code]
    if _code in _FILTER_STATE:
        STRINGS[_code]["filter_state"] = _FILTER_STATE[_code]
    if _code in _FILTER_STATE_PLACEHOLDER:
        STRINGS[_code]["filter_state_placeholder"] = _FILTER_STATE_PLACEHOLDER[_code]
    if _code in _FILTER_ZIP_LOCKED:
        STRINGS[_code]["filter_zip_locked"] = _FILTER_ZIP_LOCKED[_code]
    if _code in _OPEN_NOW:
        STRINGS[_code]["open_now_chip"] = _OPEN_NOW[_code]
    if _code in _VOICE_FALLBACK:
        STRINGS[_code]["voice_fallback_note"] = _VOICE_FALLBACK[_code]

# Specialty / service chips (English canonical → per-language)
_GLOSSARY = {
    "healthcare": {
        "es": "Salud", "ar": "الرعاية الصحية", "fr": "Santé", "pl": "Opieka zdrowotna",
        "zh": "医疗", "ur": "صحت", "hi": "स्वास्थ्य", "uk": "Охорона здоров'я", "sw": "Afya",
    },
    "education": {
        "es": "Educación", "ar": "التعليم", "fr": "Éducation", "pl": "Edukacja",
        "zh": "教育", "ur": "تعلیم", "hi": "शिक्षा", "uk": "Освіта", "sw": "Elimu",
    },
    "legal & shelter": {
        "es": "Legal y refugio", "ar": "قانوني ومأوى", "fr": "Juridique et abri", "pl": "Prawo i schronienie",
        "zh": "法律与收容", "ur": "قانونی و پناہ", "hi": "कानूनी और आश्रय", "uk": "Право і притулок", "sw": "Sheria na hifadhi",
    },
    "primary care": {
        "es": "Atención primaria", "ar": "الرعاية الأولية", "fr": "Soins primaires", "pl": "Podstawowa opieka",
        "zh": "初级保健", "ur": "بنیادی نگہداشت", "hi": "प्राथमिक देखभाल", "uk": "Первинна допомога", "sw": "Huduma ya msingi",
    },
    "adult primary care": {
        "es": "Atención primaria adultos", "ar": "رعاية أولية للبالغين", "fr": "Soins primaires adultes",
        "pl": "Opieka podstawowa (dorośli)", "zh": "成人初级保健", "ur": "بالغوں کی بنیادی نگہداشت",
        "hi": "वयस्क प्राथमिक देखभाल", "uk": "Первинна допомога (дорослі)", "sw": "Huduma ya msingi (watu wazima)",
    },
    "women's health": {
        "es": "Salud de la mujer", "ar": "صحة المرأة", "fr": "Santé des femmes", "pl": "Zdrowie kobiet",
        "zh": "女性健康", "ur": "خواتین کی صحت", "hi": "महिला स्वास्थ्य", "uk": "Жіноче здоров'я", "sw": "Afya ya wanawake",
    },
    "dental": {
        "es": "Dental", "ar": "أسنان", "fr": "Dentaire", "pl": "Dentystyka",
        "zh": "牙科", "ur": "دانت", "hi": "दंत", "uk": "Стоматологія", "sw": "Meno",
    },
    "mental health": {
        "es": "Salud mental", "ar": "الصحة النفسية", "fr": "Santé mentale", "pl": "Zdrowie psychiczne",
        "zh": "心理健康", "ur": "ذہنی صحت", "hi": "मानसिक स्वास्थ्य", "uk": "Психічне здоров'я", "sw": "Afya ya akili",
    },
    "pediatrics": {
        "es": "Pediatría", "ar": "طب الأطفال", "fr": "Pédiatrie", "pl": "Pediatria",
        "zh": "儿科", "ur": "اطفال", "hi": "बाल रोग", "uk": "Педіатрія", "sw": "Watoto",
    },
    "cardiology": {
        "es": "Cardiología", "ar": "قلب", "fr": "Cardiologie", "pl": "Kardiologia",
        "zh": "心脏病", "ur": "دل", "hi": "हृदय रोग", "uk": "Кардіологія", "sw": "Moyo",
    },
    "obstetrics/gynecology": {
        "es": "Obstetricia/Ginecología", "ar": "نساء وتوليد", "fr": "Obstétrique/Gynécologie",
        "pl": "Położnictwo/Ginekologia", "zh": "妇产科", "ur": "نسائی امراض", "hi": "प्रसूति/स्त्री रोग",
        "uk": "Акушерство/гінекологія", "sw": "Uzazi",
    },
    "endocrinology": {
        "es": "Endocrinología", "ar": "غدد صماء", "fr": "Endocrinologie", "pl": "Endokrynologia",
        "zh": "内分泌", "ur": "ہارمونز", "hi": "अंतःस्रावी", "uk": "Ендокринологія", "sw": "Homoni",
    },
    "pulmonology": {
        "es": "Neumología", "ar": "رئة", "fr": "Pneumologie", "pl": "Pulmonologia",
        "zh": "肺科", "ur": "پھیپھڑے", "hi": "फेफड़े", "uk": "Пульмонологія", "sw": "Mapafu",
    },
    "free": {
        "es": "Gratis", "ar": "مجاني", "fr": "Gratuit", "pl": "Bezpłatne",
        "zh": "免费", "ur": "مفت", "hi": "मुफ़्त", "uk": "Безкоштовно", "sw": "Bure",
    },
    "nutrition": {
        "es": "Nutrición", "ar": "تغذية", "fr": "Nutrition", "pl": "Żywienie",
        "zh": "营养", "ur": "غذائیت", "hi": "पोषण", "uk": "Харчування", "sw": "Lishe",
    },
    "behavioral health": {
        "es": "Salud conductual", "ar": "الصحة السلوكية", "fr": "Santé comportementale",
        "pl": "Zdrowie behawioralne", "zh": "行为健康", "ur": "رویے کی صحت", "hi": "व्यवहार स्वास्थ्य",
        "uk": "Поведінкове здоров'я", "sw": "Afya ya tabia",
    },
    "midwifery": {
        "es": "Partería", "ar": "قابلة", "fr": "Sage-femme", "pl": "Położnictwo",
        "zh": "助产", "ur": "دایہ", "hi": "दाईगीरी", "uk": "Акушерство", "sw": "Ukunga",
    },
    "ryan white hiv/aids program": {
        "es": "Programa Ryan White VIH/SIDA", "ar": "برنامج رايان وايت لفيروس نقص المناعة",
        "fr": "Programme Ryan White VIH/sida", "pl": "Program Ryan White HIV/AIDS",
        "zh": "Ryan White 艾滋病项目", "ur": "رائن وائٹ ایچ آئی وی پروگرام",
        "hi": "रायन व्हाइट एचआईवी कार्यक्रम", "uk": "Програма Ryan White ВІЛ/СНІД",
        "sw": "Programu ya Ryan White VVU",
    },
}

# Spoken-language labels on cards
_LANG_NAMES = {
    "english": {
        "es": "inglés", "ar": "الإنجليزية", "fr": "anglais", "pl": "angielski",
        "zh": "英语", "ur": "انگریزی", "hi": "अंग्रेज़ी", "uk": "англійська", "sw": "Kiingereza",
    },
    "spanish": {
        "es": "español", "ar": "الإسبانية", "fr": "espagnol", "pl": "hiszpański",
        "zh": "西班牙语", "ur": "ہسپانوی", "hi": "स्पेनिश", "uk": "іспанська", "sw": "Kihispania",
    },
    "arabic": {
        "es": "árabe", "ar": "العربية", "fr": "arabe", "pl": "arabski",
        "zh": "阿拉伯语", "ur": "عربی", "hi": "अरबी", "uk": "арабська", "sw": "Kiarabu",
    },
    "urdu": {
        "es": "urdu", "ar": "الأردية", "fr": "ourdou", "pl": "urdu",
        "zh": "乌尔都语", "ur": "اردو", "hi": "उर्दू", "uk": "урду", "sw": "Kiurdu",
    },
    "mandarin": {
        "es": "mandarín", "ar": "الماندرين", "fr": "mandarin", "pl": "mandaryński",
        "zh": "普通话", "ur": "مینڈرین", "hi": "मैंडरिन", "uk": "мандаринська", "sw": "Kimandarin",
    },
    "chinese": {
        "es": "chino", "ar": "الصينية", "fr": "chinois", "pl": "chiński",
        "zh": "中文", "ur": "چینی", "hi": "चीनी", "uk": "китайська", "sw": "Kichina",
    },
    "french": {
        "es": "francés", "ar": "الفرنسية", "fr": "français", "pl": "francuski",
        "zh": "法语", "ur": "فرانسیسی", "hi": "फ़्रेंच", "uk": "французька", "sw": "Kifaransa",
    },
    "polish": {
        "es": "polaco", "ar": "البولندية", "fr": "polonais", "pl": "polski",
        "zh": "波兰语", "ur": "پولش", "hi": "पोलिश", "uk": "польська", "sw": "Kipolandi",
    },
    "hindi": {
        "es": "hindi", "ar": "الهندية", "fr": "hindi", "pl": "hindi",
        "zh": "印地语", "ur": "ہندی", "hi": "हिन्दी", "uk": "гінді", "sw": "Kihindi",
    },
    "ukrainian": {
        "es": "ucraniano", "ar": "الأوكرانية", "fr": "ukrainien", "pl": "ukraiński",
        "zh": "乌克兰语", "ur": "یوکرینی", "hi": "यूक्रेनी", "uk": "українська", "sw": "Kiukreni",
    },
    "swahili": {
        "es": "suajili", "ar": "السواحيلية", "fr": "swahili", "pl": "suahili",
        "zh": "斯瓦希里语", "ur": "سواحلی", "hi": "स्वाहिली", "uk": "суахілі", "sw": "Kiswahili",
    },
    "yoruba": {
        "es": "yoruba", "ar": "اليوروبا", "fr": "yoruba", "pl": "joruba",
        "zh": "约鲁巴语", "ur": "یوروبا", "hi": "योरूबा", "uk": "йоруба", "sw": "Kiyoruba",
    },
    "kannada": {
        "es": "canarés", "ar": "الكانادا", "fr": "kannada", "pl": "kannada",
        "zh": "卡纳达语", "ur": "کنڑ", "hi": "कन्नड़", "uk": "каннада", "sw": "Kikannada",
    },
    "tamil": {
        "es": "tamil", "ar": "التاميلية", "fr": "tamoul", "pl": "tamilski",
        "zh": "泰米尔语", "ur": "تامل", "hi": "तमिल", "uk": "тамільська", "sw": "Kitamil",
    },
}

_DAYS = {
    "monday": {"es": "lunes", "ar": "الاثنين", "fr": "lundi", "pl": "poniedziałek", "zh": "周一", "ur": "پیر", "hi": "सोमवार", "uk": "понеділок", "sw": "Jumatatu"},
    "tuesday": {"es": "martes", "ar": "الثلاثاء", "fr": "mardi", "pl": "wtorek", "zh": "周二", "ur": "منگل", "hi": "मंगलवार", "uk": "вівторок", "sw": "Jumanne"},
    "wednesday": {"es": "miércoles", "ar": "الأربعاء", "fr": "mercredi", "pl": "środa", "zh": "周三", "ur": "بدھ", "hi": "बुधवार", "uk": "середа", "sw": "Jumatano"},
    "thursday": {"es": "jueves", "ar": "الخميس", "fr": "jeudi", "pl": "czwartek", "zh": "周四", "ur": "جمعرات", "hi": "गुरुवार", "uk": "четвер", "sw": "Alhamisi"},
    "friday": {"es": "viernes", "ar": "الجمعة", "fr": "vendredi", "pl": "piątek", "zh": "周五", "ur": "جمعہ", "hi": "शुक्रवार", "uk": "п'ятниця", "sw": "Ijumaa"},
    "saturday": {"es": "sábado", "ar": "السبت", "fr": "samedi", "pl": "sobota", "zh": "周六", "ur": "ہفتہ", "hi": "शनिवार", "uk": "субота", "sw": "Jumamosi"},
    "sunday": {"es": "domingo", "ar": "الأحد", "fr": "dimanche", "pl": "niedziela", "zh": "周日", "ur": "اتوار", "hi": "रविवार", "uk": "неділя", "sw": "Jumapili"},
    "mon": {"es": "lun", "ar": "الإثنين", "fr": "lun", "pl": "pon", "zh": "周一", "ur": "پیر", "hi": "सोम", "uk": "пн", "sw": "Jtatu"},
    "tue": {"es": "mar", "ar": "الثلاثاء", "fr": "mar", "pl": "wt", "zh": "周二", "ur": "منگل", "hi": "मंगल", "uk": "вт", "sw": "Jnne"},
    "wed": {"es": "mié", "ar": "الأربعاء", "fr": "mer", "pl": "śr", "zh": "周三", "ur": "بدھ", "hi": "बुध", "uk": "ср", "sw": "Jtano"},
    "thu": {"es": "jue", "ar": "الخميس", "fr": "jeu", "pl": "czw", "zh": "周四", "ur": "جمعرات", "hi": "गुरु", "uk": "чт", "sw": "Alh"},
    "fri": {"es": "vie", "ar": "الجمعة", "fr": "ven", "pl": "pt", "zh": "周五", "ur": "جمعہ", "hi": "शुक्र", "uk": "пт", "sw": "Ijm"},
    "sat": {"es": "sáb", "ar": "السبت", "fr": "sam", "pl": "sob", "zh": "周六", "ur": "ہفتہ", "hi": "शनि", "uk": "сб", "sw": "Jmosi"},
    "sun": {"es": "dom", "ar": "الأحد", "fr": "dim", "pl": "ndz", "zh": "周日", "ur": "اتوار", "hi": "रवि", "uk": "нд", "sw": "Jpili"},
}

_HOURS_PHRASES = {
    "open": {"es": "Abierto", "ar": "مفتوح", "fr": "Ouvert", "pl": "Otwarte", "zh": "开放", "ur": "کھلا", "hi": "खुला", "uk": "Відкрито", "sw": "Wazi"},
    "closed": {"es": "Cerrado", "ar": "مغلق", "fr": "Fermé", "pl": "Zamknięte", "zh": "关闭", "ur": "بند", "hi": "बंद", "uk": "Закрито", "sw": "Imefungwa"},
    "days/month": {"es": "días/mes", "ar": "أيام/شهر", "fr": "jours/mois", "pl": "dni/miesiąc", "zh": "天/月", "ur": "دن/مہینہ", "hi": "दिन/माह", "uk": "днів/місяць", "sw": "siku/mwezi"},
    "of the month": {"es": "del mes", "ar": "من الشهر", "fr": "du mois", "pl": "miesiąca", "zh": "每月", "ur": "مہینے کا", "hi": "महीने का", "uk": "місяця", "sw": "ya mwezi"},
    "hours": {"es": "Horario", "ar": "الساعات", "fr": "Horaires", "pl": "Godziny", "zh": "时间", "ur": "اوقات", "hi": "समय", "uk": "Години", "sw": "Saa"},
}


def localize_term(term: str, lang: str = "en") -> str:
    """Translate a specialty chip / short label when we know it; else keep original."""
    lang = normalize_lang(lang)
    raw = (term or "").strip()
    if not raw or lang == "en":
        return raw
    key = re.sub(r"\s+", " ", raw.lower())
    entry = _GLOSSARY.get(key)
    if entry and lang in entry:
        return entry[lang]
    # Try each semicolon-separated bit
    if ";" in raw or "/" in raw and key not in _GLOSSARY:
        parts = re.split(r"\s*[;/]\s*", raw)
        if len(parts) > 1:
            return "/".join(localize_term(p, lang) for p in parts if p.strip())
    return raw


def localize_language_list(langs, lang: str = "en") -> str:
    """Localize 'english, arabic, urdu' style lists for the UI language."""
    lang = normalize_lang(lang)
    if isinstance(langs, list):
        items = [str(x).strip() for x in langs if str(x).strip()]
    else:
        items = [p.strip() for p in re.split(r"[,;/|]+", str(langs or "")) if p.strip()]
    if not items:
        return ""
    if lang == "en":
        return ", ".join(items)
    out = []
    for item in items:
        key = item.lower()
        entry = _LANG_NAMES.get(key)
        out.append(entry[lang] if entry and lang in entry else item)
    return ", ".join(out)


def localize_hours(hours: str, lang: str = "en") -> str:
    """Localize day names and common hour phrases; leave times as-is."""
    lang = normalize_lang(lang)
    text = (hours or "").strip()
    if not text or lang == "en":
        return text

    def repl_day(m):
        word = m.group(0)
        key = word.lower()
        entry = _DAYS.get(key)
        if entry and lang in entry:
            loc = entry[lang]
            # Preserve simple Title Case for long day names when source was titled
            if word[0].isupper() and len(word) > 3 and lang in ("es", "fr", "pl", "uk", "sw"):
                return loc[:1].upper() + loc[1:]
            return loc
        return word

    text = re.sub(
        r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
        repl_day,
        text,
        flags=re.I,
    )
    for en, table in _HOURS_PHRASES.items():
        if lang in table:
            text = re.sub(re.escape(en), table[lang], text, flags=re.I)
    return text


def results_intro(
    category: str,
    query: str,
    lang: str = "en",
    *,
    zip_code: str | None = None,
    service: str | None = None,
) -> str:
    """Pip search intro in the active UI language."""
    lang = normalize_lang(lang)
    cat = category_display(category, lang)
    q = (query or "").strip() or "…"
    where = ""
    if zip_code:
        where += t("results_near", lang, z=zip_code)
    if service:
        where += t("results_for_svc", lang, svc=service)
    return t("results_intro", lang, category=cat, q=q, where=where)
