from django import forms
from django.forms import widgets


class SystemMessageAdminForm(forms.ModelForm):
    class Meta:
        fields = "__all__"
        widgets = {
            "background_color": widgets.TextInput(attrs={"type": "color"}),
            "text_color": widgets.TextInput(attrs={"type": "color"}),
        }
