from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from .models import Task, VIPLevel

User = get_user_model()

class RegisterForm(forms.ModelForm):
    """
    Formulaire d'inscription personnalisé.
    Gère le nom d'utilisateur, le téléphone, le code d'invitation et les mots de passe.
    """
    username = forms.CharField(required=True)
    phone_number = forms.CharField(max_length=15, required=True, label="Numéro Mobile")
    invitation_code_input = forms.CharField(
        max_length=10, 
        required=True, 
        label="Code de parrainage"
    )
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True, label="Confirmer le mot de passe")

    class Meta:
        model = User
        fields = ('username', 'phone_number', 'password')

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if not phone.isdigit() or len(phone) != 9 or not phone.startswith(('6', '2')):
            raise forms.ValidationError("Veuillez entrer un numéro camerounais valide (9 chiffres, ex: 6XXXXXXXX).")
        if User.objects.filter(phone_number=phone).exists():
            raise forms.ValidationError("Ce numéro est déjà utilisé.")
        return phone

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if len(password) < 6:
            raise forms.ValidationError("Le mot de passe doit contenir au moins 6 caractères.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        
        invitation_code = self.cleaned_data.get('invitation_code_input')
        if invitation_code:
            try:
                referrer = User.objects.get(invitation_code=invitation_code)
                user.referred_by = referrer
            except User.DoesNotExist:
                raise forms.ValidationError("Ce code de parrainage n'existe pas. Vérifiez et réessayez.")
        
        if commit:
            user.save()
        return user

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'autofocus': True}))
    password = forms.CharField(widget=forms.PasswordInput)

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'platform', 'category', 'link', 'is_automatic', 'requires_link_proof']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm', 'placeholder': 'Ex: Suivre notre TikTok'}),
            'description': forms.Textarea(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm', 'rows': 3, 'placeholder': 'Instructions pour l\'utilisateur...'}),
            'platform': forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm'}),
            'category': forms.Select(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm'}),
            'link': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm', 'placeholder': 'https://...'}),
            'is_automatic': forms.CheckboxInput(attrs={'class': 'w-5 h-5 rounded border-gray-300 text-red-600 focus:ring-red-500'}),
            'requires_link_proof': forms.CheckboxInput(attrs={'class': 'w-5 h-5 rounded border-gray-300 text-red-600 focus:ring-red-500'}),
        }

class VIPLevelForm(forms.ModelForm):
    class Meta:
        model = VIPLevel
        fields = ['name', 'price', 'daily_mining_reward', 'daily_task_limit', 'task_reward_rate', 'referral_reward', 'validity_days', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm', 'placeholder': 'Ex: VIP 1'}),
            'price': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm'}),
            'daily_mining_reward': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm'}),
            'daily_task_limit': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm'}),
            'task_reward_rate': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm'}),
            'referral_reward': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm'}),
            'validity_days': forms.NumberInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm'}),
            'image': forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-2xl border border-gray-100 focus:border-red-500 focus:outline-none text-sm', 'placeholder': 'fas fa-crown'}),
        }
