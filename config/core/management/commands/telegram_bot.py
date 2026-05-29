import os
import telebot
from telebot import types
from django.core.management.base import BaseCommand
from core.models import CustomUser
from django.conf import settings

TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

class Command(BaseCommand):
    help = 'Lance le bot Telegram pour la vérification OTP'

    def handle(self, *args, **options):
        bot = telebot.TeleBot(TOKEN)
        self.stdout.write(self.style.SUCCESS("Bot Telegram démarré..."))

        @bot.message_handler(commands=['start', 'help'])
        def send_welcome(message):
            markup = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
            button = types.KeyboardButton("🔐 Vérifier mon numéro", request_contact=True)
            markup.add(button)
            
            bot.reply_to(
                message, 
                "Bienvenue sur le Bot de Vérification GainTime !\n\n"
                "Pour recevoir votre code de validation ou réinitialiser votre mot de passe, "
                "cliquez sur le bouton ci-dessous pour partager votre numéro.",
                reply_markup=markup
            )

        @bot.message_handler(content_types=['contact'])
        def handle_contact(message):
            if message.contact is not None:
                phone = message.contact.phone_number
                # Nettoyage du numéro (enlever le + si présent)
                clean_phone = phone.replace("+", "")
                
                # Certains numéros camerounais arrivent avec 237, d'autres non
                # On essaie de trouver l'utilisateur avec ou sans le préfixe
                user = CustomUser.objects.filter(phone_number__icontains=clean_phone[-9:]).first()
                
                if user:
                    if user.otp_code:
                        bot.reply_to(
                            message, 
                            f"✅ Compte trouvé !\n\n"
                            f"Votre code de vérification est : *{user.otp_code}*\n\n"
                            f"Saisissez-le sur le site pour valider votre compte.",
                            parse_mode="Markdown"
                        )
                    else:
                        # Si l'utilisateur n'a pas d'OTP (déjà vérifié), on peut lui proposer un reset
                        bot.reply_to(
                            message,
                            "Votre compte est déjà vérifié. Si vous avez besoin de réinitialiser votre mot de passe, "
                            "faites-le depuis le site pour générer un nouveau code."
                        )
                else:
                    bot.reply_to(
                        message, 
                        f"❌ Aucun compte trouvé pour le numéro {clean_phone}.\n\n"
                        "Veuillez vous inscrire sur le site avec ce numéro exact avant de demander un code."
                    )

        bot.infinity_polling()
