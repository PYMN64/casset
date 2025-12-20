from django import forms

from .models import Album


class AlbumForm(forms.ModelForm):
    class Meta:
        model = Album
        fields = ("kind", "title", "description", "cover", "is_public")

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("عنوان الزامی است")
        if len(title) > 140:
            raise forms.ValidationError("عنوان طولانی است")
        return title
