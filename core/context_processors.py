import random
from .models import Transaction, CustomUser
from django.db.models import Q

def live_activity(request):
    """
    Génère un flux d'activité mélangé (Réel + Fictif) avec style camerounais.
    """
    # Noms pour le contenu fictif (quand il n'y a pas assez de données réelles)
    fake_names = [
        "Moussa", "Eto'o", "Kamga", "Abena", "Fofana", "Nguema", "Talla", "Ebollo", 
        "Ngando", "Atangana", "Zra", "Djomo", "Mbarga", "Sani", "Bello", "Kouam",
        "Tchinda", "Oumarou", "Nekdem", "Simoni", "FOTSO", "Nana", "Biya", "Eone"
    ]
    
    activities = []

    # 1. RÉCUPÉRATION DES DONNÉES RÉELLES
    # Dernières transactions réussies (Retraits, VIP, Dépôts)
    real_transactions = Transaction.objects.filter(status='COMPLETED').order_by('-created_at')[:5]
    for tx in real_transactions:
        # On masque le milieu du nom pour la vie privée
        user_display = f"{tx.user.username[:3]}***"
        if tx.transaction_type == 'WITHDRAWAL':
            msg = f"{user_display} vient de retirer {int(tx.amount)} FCFA"
        elif tx.transaction_type == 'VIP_PURCHASE':
            msg = f"{user_display} a activé un nouveau pack VIP"
        elif tx.transaction_type == 'DEPOSIT':
            msg = f"{user_display} a rechargé son compte avec succès"
        else:
            continue
        activities.append(msg)

    # Derniers inscrits
    recent_users = CustomUser.objects.order_by('-created_at')[:5]
    for u in recent_users:
        activities.append(f"{u.username[:3]}*** vient de rejoindre GainTime")

    # 2. CONTENU FICTIF (pour que le flux soit toujours riche au lancement)
    vips = ["VIP 1", "VIP 2", "VIP 3", "VIP 4"]
    amounts = [1000, 2500, 5000, 10000, 20000]
    
    while len(activities) < 15:
        name = random.choice(fake_names)
        action = random.choice([
            f"{name[:3]}*** vient de retirer {random.choice(amounts)} FCFA",
            f"{name[:3]}*** a activé le pack {random.choice(vips)}",
            f"{name[:3]}*** vient de collecter ses gains de minage",
            f"{name[:3]}*** a parrainé un nouveau membre"
        ])
        activities.append(action)
    
    # Mélanger pour que le réel et le faux soient entremêlés
    random.shuffle(activities)
    
    return {'live_activities': activities}