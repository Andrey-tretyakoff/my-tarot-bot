import time
import logging
import urllib.parse

EN_NAMES = {
    "Шут": "The Fool", "Маг": "The Magician", "Верховная Жрица": "High Priestess",
    "Императрица": "The Empress", "Император": "The Emperor", "Иерофант": "The Hierophant",
    "Влюблённые": "The Lovers", "Колесница": "The Chariot", "Сила": "Strength",
    "Отшельник": "The Hermit", "Колесо Фортуны": "Wheel of Fortune", "Справедливость": "Justice",
    "Повешенный": "The Hanged Man", "Смерть": "Death", "Умеренность": "Temperance",
    "Дьявол": "The Devil", "Башня": "The Tower", "Звезда": "The Star",
    "Луна": "The Moon", "Солнце": "The Sun", "Суд": "Judgement", "Мир": "The World",
    "Туз Жезлы": "Ace of Wands", "2 Жезлы": "Two of Wands", "3 Жезлы": "Three of Wands",
    "4 Жезлы": "Four of Wands", "5 Жезлы": "Five of Wands", "6 Жезлы": "Six of Wands",
    "7 Жезлы": "Seven of Wands", "8 Жезлы": "Eight of Wands", "9 Жезлы": "Nine of Wands",
    "10 Жезлы": "Ten of Wands", "Паж Жезлы": "Page of Wands", "Рыцарь Жезлы": "Knight of Wands",
    "Королева Жезлы": "Queen of Wands", "Король Жезлы": "King of Wands",
    "Туз Кубки": "Ace of Cups", "2 Кубки": "Two of Cups", "3 Кубки": "Three of Cups",
    "4 Кубки": "Four of Cups", "5 Кубки": "Five of Cups", "6 Кубки": "Six of Cups",
    "7 Кубки": "Seven of Cups", "8 Кубки": "Eight of Cups", "9 Кубки": "Nine of Cups",
    "10 Кубки": "Ten of Cups", "Паж Кубки": "Page of Cups", "Рыцарь Кубки": "Knight of Cups",
    "Королева Кубки": "Queen of Cups", "Король Кубки": "King of Cups",
    "Туз Мечи": "Ace of Swords", "2 Мечи": "Two of Swords", "3 Мечи": "Three of Swords",
    "4 Мечи": "Four of Swords", "5 Мечи": "Five of Swords", "6 Мечи": "Six of Swords",
    "7 Мечи": "Seven of Swords", "8 Мечи": "Eight of Swords", "9 Мечи": "Nine of Swords",
    "10 Мечи": "Ten of Swords", "Паж Мечи": "Page of Swords", "Рыцарь Мечи": "Knight of Swords",
    "Королева Мечи": "Queen of Swords", "Король Мечи": "King of Swords",
    "Туз Пентакли": "Ace of Pentacles", "2 Пентакли": "Two of Pentacles", "3 Пентакли": "Three of Pentacles",
    "4 Пентакли": "Four of Pentacles", "5 Пентакли": "Five of Pentacles", "6 Пентакли": "Six of Pentacles",
    "7 Пентакли": "Seven of Pentacles", "8 Пентакли": "Eight of Pentacles", "9 Пентакли": "Nine of Pentacles",
    "10 Пентакли": "Ten of Pentacles", "Паж Пентакли": "Page of Pentacles", "Рыцарь Пентакли": "Knight of Pentacles",
    "Королева Пентакли": "Queen of Pentacles", "Король Пентакли": "King of Pentacles"
}

ORIGINAL_URLS = {
    "Шут": "https://upload.wikimedia.org/wikipedia/commons/9/90/RWS_Tarot_00_Fool.jpg",
    "Маг": "https://upload.wikimedia.org/wikipedia/commons/d/de/RWS_Tarot_01_Magician.jpg",
    "Верховная Жрица": "https://upload.wikimedia.org/wikipedia/commons/8/88/RWS_Tarot_02_High_Priestess.jpg",
    "Императрица": "https://upload.wikimedia.org/wikipedia/commons/d/d2/RWS_Tarot_03_Empress.jpg",
    "Император": "https://upload.wikimedia.org/wikipedia/commons/c/c3/RWS_Tarot_04_Emperor.jpg",
    "Иерофант": "https://upload.wikimedia.org/wikipedia/commons/8/8d/RWS_Tarot_05_Hierophant.jpg",
    "Влюблённые": "https://upload.wikimedia.org/wikipedia/commons/3/3a/TheLovers.jpg",
    "Колесница": "https://upload.wikimedia.org/wikipedia/commons/9/9b/RWS_Tarot_07_Chariot.jpg",
    "Сила": "https://upload.wikimedia.org/wikipedia/commons/f/f5/RWS_Tarot_08_Strength.jpg",
    "Отшельник": "https://upload.wikimedia.org/wikipedia/commons/4/4d/RWS_Tarot_09_Hermit.jpg",
    "Колесо Фортуны": "https://upload.wikimedia.org/wikipedia/commons/3/3c/RWS_Tarot_10_Wheel_of_Fortune.jpg",
    "Справедливость": "https://upload.wikimedia.org/wikipedia/commons/e/e0/RWS_Tarot_11_Justice.jpg",
    "Повешенный": "https://upload.wikimedia.org/wikipedia/commons/2/27/RWS_Tarot_12_Hanged_Man.jpg",
    "Смерть": "https://upload.wikimedia.org/wikipedia/commons/d/d7/RWS_Tarot_13_Death.jpg",
    "Умеренность": "https://upload.wikimedia.org/wikipedia/commons/f/f8/RWS_Tarot_14_Temperance.jpg",
    "Дьявол": "https://upload.wikimedia.org/wikipedia/commons/5/55/RWS_Tarot_15_Devil.jpg",
    "Башня": "https://upload.wikimedia.org/wikipedia/commons/5/53/RWS_Tarot_16_Tower.jpg",
    "Звезда": "https://upload.wikimedia.org/wikipedia/commons/d/db/RWS_Tarot_17_Star.jpg",
    "Луна": "https://upload.wikimedia.org/wikipedia/commons/7/7f/RWS_Tarot_18_Moon.jpg",
    "Солнце": "https://upload.wikimedia.org/wikipedia/commons/1/17/RWS_Tarot_19_Sun.jpg",
    "Суд": "https://upload.wikimedia.org/wikipedia/commons/d/dd/RWS_Tarot_20_Judgement.jpg",
    "Мир": "https://upload.wikimedia.org/wikipedia/commons/f/ff/RWS_Tarot_21_World.jpg",
    "Туз Жезлы": "https://upload.wikimedia.org/wikipedia/commons/1/19/Wands01.jpg",
    "2 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/5/52/Wands02.jpg",
    "3 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/d/d7/Wands03.jpg",
    "4 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/4/47/Wands04.jpg",
    "5 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/3/3e/Wands05.jpg",
    "6 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/9/90/Wands06.jpg",
    "7 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/4/47/Wands07.jpg",
    "8 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/6/68/Wands08.jpg",
    "9 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/2/28/Wands09.jpg",
    "10 Жезлы": "https://upload.wikimedia.org/wikipedia/commons/1/19/Wands10.jpg",
    "Паж Жезлы": "https://upload.wikimedia.org/wikipedia/commons/5/5f/WandsPage.jpg",
    "Рыцарь Жезлы": "https://upload.wikimedia.org/wikipedia/commons/d/dc/WandsKnight.jpg",
    "Королева Жезлы": "https://upload.wikimedia.org/wikipedia/commons/9/91/WandsQueen.jpg",
    "Король Жезлы": "https://upload.wikimedia.org/wikipedia/commons/c/c3/WandsKing.jpg",
    "Туз Кубки": "https://upload.wikimedia.org/wikipedia/commons/9/9b/Cups01.jpg",
    "2 Кубки": "https://upload.wikimedia.org/wikipedia/commons/b/b9/Cups02.jpg",
    "3 Кубки": "https://upload.wikimedia.org/wikipedia/commons/7/7d/Cups03.jpg",
    "4 Кубки": "https://upload.wikimedia.org/wikipedia/commons/3/35/Cups04.jpg",
    "5 Кубки": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Cups05.jpg",
    "6 Кубки": "https://upload.wikimedia.org/wikipedia/commons/d/d6/Cups06.jpg",
    "7 Кубки": "https://upload.wikimedia.org/wikipedia/commons/6/66/Cups07.jpg",
    "8 Кубки": "https://upload.wikimedia.org/wikipedia/commons/2/22/Cups08.jpg",
    "9 Кубки": "https://upload.wikimedia.org/wikipedia/commons/2/27/Cups09.jpg",
    "10 Кубки": "https://upload.wikimedia.org/wikipedia/commons/a/a2/Cups10.jpg",
    "Паж Кубки": "https://upload.wikimedia.org/wikipedia/commons/9/9b/CupsPage.jpg",
    "Рыцарь Кубки": "https://upload.wikimedia.org/wikipedia/commons/b/b1/CupsKnight.jpg",
    "Королева Кубки": "https://upload.wikimedia.org/wikipedia/commons/3/35/CupsQueen.jpg",
    "Король Кубки": "https://upload.wikimedia.org/wikipedia/commons/9/91/CupsKing.jpg",
    "Туз Мечи": "https://upload.wikimedia.org/wikipedia/commons/1/13/Swords01.jpg",
    "2 Мечи": "https://upload.wikimedia.org/wikipedia/commons/2/27/Swords02.jpg",
    "3 Мечи": "https://upload.wikimedia.org/wikipedia/commons/3/33/Swords03.jpg",
    "4 Мечи": "https://upload.wikimedia.org/wikipedia/commons/4/44/Swords04.jpg",
    "5 Мечи": "https://upload.wikimedia.org/wikipedia/commons/5/55/Swords05.jpg",
    "6 Мечи": "https://upload.wikimedia.org/wikipedia/commons/6/66/Swords06.jpg",
    "7 Мечи": "https://upload.wikimedia.org/wikipedia/commons/7/77/Swords07.jpg",
    "8 Мечи": "https://upload.wikimedia.org/wikipedia/commons/8/88/Swords08.jpg",
    "9 Мечи": "https://upload.wikimedia.org/wikipedia/commons/9/99/Swords09.jpg",
    "10 Мечи": "https://upload.wikimedia.org/wikipedia/commons/a/aa/Swords10.jpg",
    "Паж Мечи": "https://upload.wikimedia.org/wikipedia/commons/b/bb/SwordsPage.jpg",
    "Рыцарь Мечи": "https://upload.wikimedia.org/wikipedia/commons/c/cc/SwordsKnight.jpg",
    "Королева Мечи": "https://upload.wikimedia.org/wikipedia/commons/d/dd/SwordsQueen.jpg",
    "Король Мечи": "https://upload.wikimedia.org/wikipedia/commons/e/ee/SwordsKing.jpg",
    "Туз Пентакли": "https://upload.wikimedia.org/wikipedia/commons/1/11/Pents01.jpg",
    "2 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/2/22/Pents02.jpg",
    "3 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/3/33/Pents03.jpg",
    "4 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/4/44/Pents04.jpg",
    "5 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/5/55/Pents05.jpg",
    "6 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/6/66/Pents06.jpg",
    "7 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/7/77/Pents07.jpg",
    "8 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/8/88/Pents08.jpg",
    "9 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/9/99/Pents09.jpg",
    "10 Пентакли": "https://upload.wikimedia.org/wikipedia/commons/a/aa/Pents10.jpg",
    "Паж Пентакли": "https://upload.wikimedia.org/wikipedia/commons/b/bb/PentsPage.jpg",
    "Рыцарь Пентакли": "https://upload.wikimedia.org/wikipedia/commons/c/cc/PentsKnight.jpg",
    "Королева Пентакли": "https://upload.wikimedia.org/wikipedia/commons/d/dd/PentsQueen.jpg",
    "Король Пентакли": "https://upload.wikimedia.org/wikipedia/commons/e/ee/PentsKing.jpg",
}

RWS_COMPOSITIONS = {
    # Жезлы
    "Туз Жезлы": "A hand emerging from a cloud grasping a sprouting wooden wand with leaves. Castle in background on mountain. New creative energy. STRICTLY NO horses.",
    "2 Жезлы": "A noble figure in red robes standing on castle battlements holding a globe in left hand, right hand holds wand. One wand fixed to wall. Looking at mountains and river. Planning future. STRICTLY NO horses.",
    "3 Жезлы": "A figure in orange robes standing on cliff edge looking at two ships on sea. One wand held upright in right hand, two wands planted in ground behind. Expansion and foresight. STRICTLY NO horses.",
    "4 Жезлы": "Four large wands forming a canopy decorated with garlands and flowers. Two figures in foreground holding bouquets, celebrating. Castle in background with people on balcony. Harmony, home, celebration. STRICTLY NO horses.",
    "5 Жезлы": "Five young men in different colored clothes wielding wooden wands in mock combat, all standing on ground in chaotic positions. Competition and conflict. STRICTLY NO horses.",
    "6 Жезлы": "A figure in armor on white horse wearing victory wreath, holding wand with wreath attached. Crowd behind holding wands with wreaths. Victory parade and recognition. THIS CARD HAS A HORSE.",
    "7 Жезлы": "A figure standing on high ground defending with one wand held up against six wands attacking from below. Perseverance and defense. STRICTLY NO horses.",
    "8 Жезлы": "Eight wands flying through air in parallel toward ground. Stream and landscape below. Swift action and messages. STRICTLY NO people, NO horses.",
    "9 Жезлы": "A wounded figure with bandaged head leaning on one wand, eight wands planted upright behind forming barrier. Cautious stance. Resilience. STRICTLY NO horses.",
    "10 Жезлы": "A figure carrying ten heavy wands in arms toward distant town, back bent under burden. Oppression and hard work. STRICTLY NO horses.",
    "Паж Жезлы": "A young figure with blond hair standing on barren ground holding wand upright with both hands, looking at it admiringly. Desert landscape with cacti. New ideas and enthusiasm. STRICTLY NO horses.",
    "Рыцарь Жезлы": "A knight in armor charging on a galloping brown horse through desert, holding wand raised high. Fiery energy and action. THIS CARD HAS A GALLOPING HORSE.",
    "Королева Жезлы": "A queen with red hair sitting on stone throne holding wand upright, black cat at feet. Sunflowers on throne. Confident and warm. STRICTLY NO horses.",
    "Король Жезлы": "A king with brown beard sitting on throne holding wand upright, wearing robes with salamander emblem. Lizard on throne. Visionary leader. STRICTLY NO horses.",

    # Кубки
    "Туз Кубки": "A hand emerging from cloud holding ornate golden cup from which water overflows in five streams. Dove descending with wafer in beak. Lotus leaves on water. Love and intuition. STRICTLY NO horses.",
    "2 Кубки": "A young man and woman exchanging cups, caduceus symbol above them between cups. Lion head on fountain. Partnership and attraction. STRICTLY NO horses.",
    "3 Кубки": "Three young women in flowing robes raising golden cups in celebration, fruits and flowers around them on ground. Friendship and joy. STRICTLY NO horses.",
    "4 Кубки": "A figure sitting under tree with arms crossed, three cups before them on ground, fourth cup offered by hand from cloud. Contemplation and apathy. STRICTLY NO horses.",
    "5 Кубки": "A cloaked figure in black looking down at three spilled cups, two cups standing behind them. Bridge and castle in distance across river. Loss and regret. STRICTLY NO horses.",
    "6 Кубки": "Two children in courtyard, one offering cup filled with flowers to another. Five cups with flowers around them. Nostalgia and innocence. STRICTLY NO horses.",
    "7 Кубки": "A figure facing seven cups on clouds containing various visions (jewels, snake, dragon, castle, laurel wreath, head). Choice and illusion. STRICTLY NO horses.",
    "8 Кубки": "A cloaked figure walking away from eight stacked cups toward mountains and water, holding staff. Disillusionment and journey. STRICTLY NO horses.",
    "9 Кубки": "A satisfied figure in merchant clothes sitting with arms crossed, nine cups arranged in row behind on bench. Contentment and wishes fulfilled. STRICTLY NO horses.",
    "10 Кубки": "A happy family (couple and two children) with arms raised, ten cups forming rainbow above them. Cottage and trees in background. Emotional fulfillment. STRICTLY NO horses.",
    "Паж Кубки": "A young figure with blond hair holding cup with fish emerging from it, looking at fish with curiosity. Coastal landscape with waves. Creative messages. STRICTLY NO horses.",
    "Рыцарь Кубки": "A knight in armor riding a walking horse (not galloping) holding cup with both hands, wearing winged helmet. Gentle and romantic. THIS CARD HAS A WALKING HORSE.",
    "Королева Кубки": "A queen with gentle expression sitting on throne by water, holding ornate cup, looking at it. Cherubs carved on throne. Compassionate and intuitive. STRICTLY NO horses.",
    "Король Кубки": "A king sitting on throne in sea holding cup in right hand and scepter in left, fish carved on throne. Ship and dolphin in water. Emotional mastery. STRICTLY NO horses.",

    # Мечи
    "Туз Мечи": "A hand emerging from cloud grasping an upright sword crowned with golden wreath. Clouds and crown above. Mental clarity. STRICTLY NO horses.",
    "2 Мечи": "A blindfolded figure in white robes sitting on stone bench holding two crossed swords. Moonlit water behind with rocks. Stalemate and difficult choice. STRICTLY NO horses.",
    "3 Мечи": "A red heart pierced by exactly three swords. Heavy rain and storm clouds behind. Heartbreak and sorrow. STRICTLY NO horses, NO people.",
    "4 Мечи": "A knight in armor lying in prayer on tomb, hands together. Three swords hang above on wall, one sword below tomb. Stained glass window. Rest and recovery. STRICTLY NO horses.",
    "5 Мечи": "A smug figure holding three swords, two swords on ground. Two defeated figures walking away in distance. Cloudy sky. Hollow victory. STRICTLY NO horses.",
    "6 Мечи": "A cloaked ferryman poling boat with standing figure and seated grieving figure with back turned. Six swords stuck in boat. Calm water transitioning to rough. Transition. STRICTLY NO horses.",
    "7 Мечи": "A figure sneaking away from camp carrying five swords in arms, leaving two swords upright in ground. Tent and landscape in background. Stealth and strategy. STRICTLY NO horses.",
    "8 Мечи": "A bound and blindfolded figure standing in mud surrounded by exactly eight swords planted point-down in circle. Distant castle on cliff. Restriction. STRICTLY NO horses.",
    "9 Мечи": "A figure sitting upright in bed with face buried in hands in despair. Exactly nine swords hang vertically on dark wall behind in row. Zodiac tapestry on bed. Anxiety and nightmares. STRICTLY NO horses, NO riders, NO outdoor scenes.",
    "10 Мечи": "A figure lying face-down on barren ground with exactly ten swords pierced through back. Dark stormy sky above, golden dawn on horizon. Ultimate ending. STRICTLY NO horses, NO riders.",
    "Паж Мечи": "A young figure standing on uneven ground holding sword upright with both hands, looking alert. Windy landscape with clouds and broken trees. Vigilance. STRICTLY NO horses.",
    "Рыцарь Мечи": "An armored knight charging on galloping white horse through stormy clouds, sword raised high overhead. Dynamic and aggressive. THIS CARD HAS A GALLOPING HORSE.",
    "Королева Мечи": "A stern queen with serious expression sitting on stone throne holding sword upright in right hand, left hand extended. Clouds parting, butterflies on throne. Clear intellect. STRICTLY NO horses.",
    "Король Мечи": "An authoritative king sitting on stone throne holding sword upright in right hand. Decisive and logical. Clear sky and butterflies. Justice and authority. STRICTLY NO horses.",

    # Пентакли
    "Туз Пентакли": "A hand emerging from cloud holding large golden pentacle with pentagram. Garden path leading to mountains and archway. Prosperity and new opportunity. STRICTLY NO horses.",
    "2 Пентакли": "A young figure juggling two pentacles connected by infinity symbol (lemniscate). Ships on rough sea in background with waves. Adaptation and balance. STRICTLY NO horses.",
    "3 Пентакли": "A craftsman carving pentacle in cathedral, two monks holding plans looking at him. Three pentacles visible in arches. Teamwork and skill. STRICTLY NO horses.",
    "4 Пентакли": "A figure clutching one pentacle to chest with arms, one pentacle on head, two pentacles under feet. City walls behind. Control and conservation. STRICTLY NO horses.",
    "5 Пентакли": "Two impoverished figures walking in snow past stained glass window with five pentacles. One on crutches. Hardship and isolation. STRICTLY NO horses.",
    "6 Пентакли": "A merchant in robes holding scales giving pentacles from bag to two kneeling beggars. Nine pentacles visible. Generosity and balance. STRICTLY NO horses.",
    "7 Пентакли": "A figure leaning on hoe looking thoughtfully at pentacles growing on bush. Six pentacles visible. Distant landscape. Patience and investment. STRICTLY NO horses.",
    "8 Пентакли": "A craftsman carving pentacles at bench, six finished pentacles displayed, one pentacle being worked on. Diligence and skill. STRICTLY NO horses.",
    "9 Пентакли": "A refined figure in garden with nine pentacles in background on vines, hooded falcon on gloved hand. Luxury and self-sufficiency. STRICTLY NO horses.",
    "10 Пентакли": "An elderly figure with family (couple, children, dogs) in archway. Ten pentacles visible in arch and on clothes. Wealth and legacy. STRICTLY NO horses.",
    "Паж Пентакли": "A young figure holding pentacle with both hands, examining it closely with concentration. Fertile landscape with plowed field. Study and opportunity. STRICTLY NO horses.",
    "Рыцарь Пентакли": "A knight sitting motionless on a stationary black horse (not moving) holding pentacle with both hands. Peaceful farmland in background. Steady and responsible. THIS CARD HAS A STATIONARY HORSE.",
    "Королева Пентакли": "A queen sitting on throne in lush garden holding pentacle, goat head carved on throne. Rabbits nearby. Nurturing and practical. STRICTLY NO horses.",
    "Король Пентакли": "A king sitting on throne decorated with bulls holding pentacle in right hand and scepter in left. Fertile landscape with castle. Wealth and stability. STRICTLY NO horses.",
}


def generate_ai_url(card_name: str) -> str:
    en_name = EN_NAMES.get(card_name, card_name)
    composition = RWS_COMPOSITIONS.get(card_name, "")

    if composition:
        prompt = f"Exact 1909 Rider-Waite-Smith tarot card: {en_name}. Scene: {composition} "
        prompt += "Style: vintage woodcut engraving with muted watercolor wash on aged parchment, flat 2D esoteric symbolism, ornamental golden border, traditional Pamela Colman Smith artwork. "
        prompt += "NO text, NO signatures, NO dates, NO 3D, NO photorealism, NO modern elements, NO anime."
    else:
        suit = card_name.split()[-1]
        prompt = f"Exact 1909 Rider-Waite-Smith tarot card: {en_name}. Classic {suit} suit composition. "
        prompt += "Style: vintage woodcut engraving, muted watercolor on parchment, flat 2D esoteric symbolism, ornamental border, traditional layout, Pamela Colman Smith style. "
        prompt += "NO text, NO signatures, NO 3D, NO photorealism, NO modern elements."

    negative = "ugly, deformed, extra limbs, text, watermark, signature, date, 3d render, photorealistic, modern clothing, cars, technology, anime, cartoon, bright neon colors, digital painting, smooth gradients"

    if "Мечи" in card_name and card_name not in ["Рыцарь Мечи"]:
        negative += ", horses, riders, knights on horseback, outdoor battle scenes, galloping"
    elif "Жезлы" in card_name and card_name not in ["Рыцарь Жезлы", "6 Жезлы"]:
        negative += ", horses, riders, knights on horseback"
    elif "Кубки" in card_name and card_name not in ["Рыцарь Кубки"]:
        negative += ", horses, riders, knights on horseback, swords, wands, pentacles, weapons"
    elif "Пентакли" in card_name and card_name not in ["Рыцарь Пентакли"]:
        negative += ", horses, riders, knights on horseback, swords, wands, cups"

    safe_prompt = urllib.parse.quote(prompt)
    safe_neg = urllib.parse.quote(negative)
    seed = int(time.time() * 1000) % 1_000_000

    return f"https://image.pollinations.ai/prompt/{safe_prompt}?width=512&height=768&seed={seed}&nologo=true&model=flux&negative_prompt={safe_neg}"


async def get_tarot_media(card_name: str) -> tuple[str, str]:
    if card_name in ORIGINAL_URLS:
        return ORIGINAL_URLS[card_name], 'original'
    return generate_ai_url(card_name), 'ai'


# Добавь этот код в конец image_gen.py

def generate_rune_image(rune_names: list[str]) -> str:
    """
    Генерирует картинку с тремя рунами
    rune_names: список из 3 названий рун на английском (например ['Fehu', 'Uruz', 'Ansuz'])
    """
    import random

    # Создаем промпт для нейросети
    rune_list = ", ".join(rune_names)

    prompt = (
        f"Mystical photo of three ancient runestones lying on mossy dark wood. "
        f"The stones are carved with runes: {rune_list}. "
        f"Soft magical blue and gold lighting, cinematic, hyperrealistic, 8k. "
        f"Top down view, flat lay style."
    )

    # Используем существующую функцию генерации (или api, если он у тебя подключен)
    # Я предполагаю, что у тебя есть функция generate_ai_url или аналогичная
    # Если нет, здесь должна быть логика вызова твоего API картинок
    try:
        # Если у тебя уже есть функция, которая принимает промпт:
        return generate_ai_url(prompt)
    except NameError:
        # Фоллбэк, если функции нет (вернет заглушку или путь)
        print(f"🎨 Генерирую руны: {prompt}")
        return "https://via.placeholder.com/800x600?text=Runes+Generated"