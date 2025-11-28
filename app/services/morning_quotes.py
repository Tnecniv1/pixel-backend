# app/services/morning_quotes.py
"""
Collection de phrases inspirantes sur la concentration et le calcul mental.
"""

import random
from typing import Dict

MORNING_QUOTES = [
    {
        "title": "🌅 Bonjour champion !",
        "body": "La concentration est la clé de tout apprentissage. Commence ta journée par un entraînement !"
    },
    {
        "title": "☀️ Nouveau jour, nouvelles victoires !",
        "body": "Un esprit entraîné est un esprit affûté. Quelques calculs pour bien démarrer ?"
    },
    {
        "title": "🧠 Réveille ton cerveau !",
        "body": "Les champions s'entraînent tous les jours. 5 minutes de calcul mental suffisent !"
    },
    {
        "title": "💪 Force mentale !",
        "body": "La concentration est comme un muscle : elle se développe avec l'entraînement régulier."
    },
    {
        "title": "🎯 Focus du matin",
        "body": "Commence ta journée avec clarté : quelques calculs pour activer ton cerveau !"
    },
    {
        "title": "⚡ Énergie mentale !",
        "body": "Le matin est le meilleur moment pour entraîner ton esprit. Es-tu prêt ?"
    },
    {
        "title": "🌟 Brille aujourd'hui !",
        "body": "Chaque entraînement te rapproche de l'excellence. Un petit effort maintenant ?"
    },
    {
        "title": "🚀 Lance ta journée !",
        "body": "La réussite est la somme de petits efforts répétés jour après jour."
    },
    {
        "title": "🔥 Allume ton cerveau !",
        "body": "Le calcul mental développe la concentration, la mémoire et la logique. À toi de jouer !"
    },
    {
        "title": "🎓 Apprends en t'amusant",
        "body": "Chaque calcul résolu est une victoire. Accumule tes victoires dès ce matin !"
    },
    {
        "title": "💎 Forge ton esprit",
        "body": "Un diamant se forme sous pression, un champion par l'entraînement quotidien."
    },
    {
        "title": "🏆 Objectif excellence",
        "body": "Les champions ne sont pas nés, ils se sont entraînés. Continue ta progression !"
    },
    {
        "title": "🌈 Journée parfaite",
        "body": "Commence par ce que tu fais de mieux : t'entraîner et progresser !"
    },
    {
        "title": "⭐ Sois au top",
        "body": "La concentration est une habitude qui se cultive chaque matin. Cultive-la !"
    },
    {
        "title": "🎪 Spectacle mental",
        "body": "Ton cerveau est capable de merveilles. Montre-lui le chemin avec du calcul !"
    },
    {
        "title": "🔮 Pouvoir mental",
        "body": "5 minutes d'entraînement = 1% de progrès. 1% chaque jour = 37x meilleur en 1 an !"
    },
    {
        "title": "🌺 Épanouis-toi",
        "body": "Le bonheur de progresser vaut tous les efforts. Un petit entraînement ?"
    },
    {
        "title": "🎨 Crée ton succès",
        "body": "Chaque jour est une nouvelle page. Écris-y une victoire en calcul mental !"
    },
    {
        "title": "🦅 Envole-toi haut",
        "body": "Les limites n'existent que dans l'esprit. Repousse-les avec l'entraînement !"
    },
    {
        "title": "🌍 Conquiers le monde",
        "body": "Un esprit fort domine tous les défis. Renforce le tien chaque matin !"
    },
    {
        "title": "⚔️ Guerrier mental",
        "body": "La concentration est ton arme secrète. Aiguise-la avec du calcul mental !"
    },
    {
        "title": "🎯 Précision maximale",
        "body": "Un esprit précis prend de meilleures décisions. Entraîne ta précision !"
    },
    {
        "title": "🧘 Zen et concentré",
        "body": "La maîtrise commence par la concentration. Quelques minutes d'entraînement ?"
    },
    {
        "title": "🎼 Harmonie mentale",
        "body": "Comme un musicien s'entraîne chaque jour, entraîne ton calcul mental !"
    },
    {
        "title": "🌠 Étoile montante",
        "body": "Tu es sur la voie de l'excellence. Continue ton ascension !"
    },
    {
        "title": "🔑 Clé du succès",
        "body": "La régularité bat le talent quand le talent ne travaille pas. Sois régulier !"
    },
    {
        "title": "🎪 Champion en herbe",
        "body": "Chaque champion a commencé par un entraînement. Le tien, c'est maintenant !"
    },
    {
        "title": "🌊 Vague de succès",
        "body": "Surfe sur ta progression. Un entraînement matinal pour rester au sommet !"
    },
    {
        "title": "🎁 Cadeau du jour",
        "body": "Offre-toi un moment d'excellence : quelques minutes de calcul mental !"
    },
    {
        "title": "🦄 Unique et fort",
        "body": "Ton cerveau est unique et puissant. Nourris-le avec du challenge !"
    }
]


def get_random_morning_quote() -> Dict[str, str]:
    """
    Retourne une phrase inspirante aléatoire pour le matin.
    """
    return random.choice(MORNING_QUOTES)


def get_morning_quote_for_streak(current_streak: int) -> Dict[str, str]:
    """
    Retourne une phrase adaptée au streak actuel de l'utilisateur.
    """
    if current_streak == 0:
        return {
            "title": "🌅 Nouveau départ !",
            "body": "Chaque grand voyage commence par un premier pas. Lance ton streak aujourd'hui !"
        }
    elif current_streak >= 30:
        return {
            "title": f"👑 {current_streak} jours de légende !",
            "body": "Tu es un véritable champion ! Continue cette série incroyable !"
        }
    elif current_streak >= 14:
        return {
            "title": f"🔥 {current_streak} jours de feu !",
            "body": "Deux semaines consécutives ! Tu es sur une lancée extraordinaire !"
        }
    elif current_streak >= 7:
        return {
            "title": f"⭐ {current_streak} jours d'excellence !",
            "body": "Une semaine complète ! L'habitude devient naturelle, continue !"
        }
    else:
        return get_random_morning_quote()