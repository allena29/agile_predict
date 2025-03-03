from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Field, Layout, Fieldset
from config.settings import GLOBAL_SETTINGS
from .models import Forecasts

REGION_CHOICES = [(r, GLOBAL_SETTINGS["REGIONS"][r]["name"]) for r in GLOBAL_SETTINGS["REGIONS"]]
forecast_choices = [(f.id, f.name) for f in Forecasts.objects.all().order_by("-created_at")][:14]


class RegionForm(forms.Form):
    region = forms.ChoiceField(choices=REGION_CHOICES)
    forecasts_to_plot = forms.MultipleChoiceField(
        initial=forecast_choices[0], widget=forms.CheckboxSelectMultiple, choices=forecast_choices
    )

    def __init__(self, region="X", *args, **kwargs):
        # print(f"form region: {region}")
        super(RegionForm, self).__init__(*args, **kwargs)
        self.fields["region"] = forms.ChoiceField(choices=REGION_CHOICES)
        # print((region, GLOBAL_SETTINGS["REGIONS"][region]["name"]))
        # print(self.fields["region"].initial)
        self.fields["region"].initial = region, GLOBAL_SETTINGS["REGIONS"][region]["name"]
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Fieldset("Select your DNO Region"),
            Field("region"),
            Field("forecasts_to_plot", small=True),
            Submit("submit", "Submit", css_class="btn btn-dark"),
        )
        # self.helper.layout = Layout(
        #     Field("region"),
        #     Field("forecasts_to_plot"),
        # )
        # self.helper.form_id = "id-exampleForm"
        # self.helper.form_class = "bg-white text-dark"
        # self.helper.form_method = "post"
        # self.helper.form_action = "submit_survey"
        # self.helper.add_input(Submit("submit", "Submit"))
