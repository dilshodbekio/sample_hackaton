"""Test PDF'larini yaratadi: tests/fixtures/namuna_nizom.pdf (matnli, 4 bet) va bosh.pdf (matnsiz).
Ishga tushirish (ai/ ichida): python tests/make_fixtures.py   (fpdf2 kerak: pip install -r requirements-dev.txt)"""

from pathlib import Path

from fpdf import FPDF

FIXTURES = Path(__file__).parent / "fixtures"
FONT = "C:/Windows/Fonts/arial.ttf"

# ʻ (U+02BB), ʼ (U+02BC), ’ (U+2019) va oddiy ' ataylab aralash ishlatilgan
PAGES = [
    (
        "1-bob. Umumiy qoidalar",
        [
            "1. Ushbu Nizom umumiy oʻrta taʼlim muassasalari pedagog xodimlarini attestatsiyadan o'tkazish "
            "tartibini belgilaydi. Attestatsiya pedagogning kasbiy malakasi, bilim darajasi va ish natijalarini "
            "baholash maqsadida o'tkaziladi.",
            "2. Attestatsiya har besh yilda kamida bir marta o’tkaziladi. Pedagog xodim o'z xohishiga ko'ra "
            "muddatidan oldin ham attestatsiyadan oʻtish uchun ariza berishi mumkin.",
            "3. Attestatsiya natijalariga koʻra pedagogga malaka toifasi beriladi yoki avval berilgan toifa "
            "tasdiqlanadi. Toifalar quyidagilardan iborat: ikkinchi toifa, birinchi toifa va oliy toifa.",
        ],
    ),
    (
        "2-bob. Malaka toifalariga qo'yiladigan talablar",
        [
            "4. Ikkinchi toifa uchun pedagog kamida ikki yillik ish stajiga ega bo'lishi, o'qitayotgan fanidan "
            "test sinovida kamida 60 foiz ball to'plashi talab etiladi.",
            "5. Birinchi toifa uchun kamida besh yillik pedagogik staj, test sinovida kamida 70 foiz ball va "
            "ochiq dars o'tkazganligi to'g'risidagi maʼlumotnoma talab qilinadi.",
            "6. Oliy toifa uchun kamida sakkiz yillik pedagogik staj, test sinovida kamida 86 foiz ball, "
            "shuningdek, oxirgi uch yil ichida respublika yoki xalqaro miqyosdagi tanlov va olimpiadalarda "
            "sovrindor oʻquvchilar tayyorlaganligi yoki metodik qoʻllanma muallifi ekanligi talab etiladi. "
            "Oliy toifaga da'vogar pedagog ilmiy-uslubiy kengashning ijobiy xulosasini taqdim etadi.",
        ],
    ),
    (
        "3-bob. Attestatsiya komissiyasi",
        [
            "7. Attestatsiya komissiyasi tuman (shahar) xalq taʼlimi boʻlimi huzurida tuziladi. Komissiya "
            "tarkibiga tajribali pedagoglar, metodistlar va kasaba uyushmasi vakili kiritiladi.",
            "8. Komissiya majlisi a'zolarining kamida uchdan ikki qismi ishtirok etganda vakolatli hisoblanadi. "
            "Qaror ochiq ovoz berish yoʻli bilan ko'pchilik ovoz bilan qabul qilinadi.",
            "9. Komissiya pedagogning portfoliosi, dars kuzatuvi natijalari va test sinovi natijalarini "
            "o’rganib chiqib, o'n kun ichida qaror qabul qiladi.",
        ],
    ),
    (
        "4-bob. Natijalar va shikoyatlar",
        [
            "10. Attestatsiya natijalari pedagogga yozma ravishda uch ish kuni ichida maʼlum qilinadi.",
            "11. Natijaga rozi bo'lmagan pedagog o'n besh kun ichida viloyat attestatsiya komissiyasiga "
            "shikoyat berishi mumkin. Shikoyat bir oy muddatda koʻrib chiqiladi.",
            "12. Attestatsiyadan o'ta olmagan pedagog bir yildan so'ng qayta attestatsiyadan o’tishi mumkin. "
            "Bu davrda unga malaka oshirish kurslarida o'qish tavsiya etiladi.",
        ],
    ),
]


def make_text_pdf(path: Path) -> None:
    pdf = FPDF()
    pdf.add_font("Arial", "", FONT)
    pdf.set_auto_page_break(False)
    for title, paragraphs in PAGES:
        pdf.add_page()
        pdf.set_font("Arial", size=15)
        pdf.multi_cell(0, 9, title)
        pdf.ln(4)
        pdf.set_font("Arial", size=12)
        for p in paragraphs:
            pdf.multi_cell(0, 7, p)
            pdf.ln(5)
    pdf.output(str(path))


def make_blank_pdf(path: Path) -> None:
    pdf = FPDF()
    for _ in range(2):
        pdf.add_page()
        pdf.set_fill_color(200, 200, 200)
        pdf.rect(30, 40, 150, 100, style="F")  # faqat grafika, matn yo'q (skaner o'rnida)
    pdf.output(str(path))


if __name__ == "__main__":
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_text_pdf(FIXTURES / "namuna_nizom.pdf")
    make_blank_pdf(FIXTURES / "bosh.pdf")
    print("yaratildi:", *sorted(p.name for p in FIXTURES.glob("*.pdf")))
