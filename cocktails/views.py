# Create your views here.
import datetime

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models.functions import Lower
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import DetailView, ListView
from django.views.generic.edit import CreateView, DeleteView, UpdateView

from .forms import CocktailForm, RegisterForm, UserForm, VoteForm
from .models import Cocktail, Ingredient, Vote


class IndexView(View):
    template_name = "cocktails/index.html"

    def get(self, request):
        cocktail = Cocktail.objects.get(
            name="Daniel is in fact making progress")
        ingredients = Ingredient.objects.filter(cocktail=cocktail)
        return render(request, template_name=self.template_name, context={
            "cocktail": cocktail,
            "ingredients": ingredients
        })


class TopFiveView(ListView):
    template_name = "cocktails/top5.html"
    context_object_name = "cocktails"

    def get_queryset(self):
        get_request = self.request.GET
        if get_request.__contains__("sort_by") and get_request["sort_by"] and get_request['sort_by'].lower() != "fresh":
            sort_param = "-" + get_request["sort_by"] + "_rating"
        else:
            sort_param = "timestamp"

        return Cocktail.objects.all().order_by("%s" % sort_param)[:5]


class AToZ(ListView):
    template_name = "cocktails/a_to_z.html"
    context_object_name = "cocktails"

    def get_queryset(self, ):
        get_request = self.request.GET
        if get_request.__contains__("sort_by") and get_request["sort_by"] != "":
            letter = get_request["sort_by"]
        else:
            letter = 'a'
        cocktails_by_letter = Cocktail.objects.filter(name__startswith=letter)
        return cocktails_by_letter.order_by(Lower("name"))


class ResultView(ListView):
    template_name = "cocktails/search_results.html"
    context_object_name = "cocktails"

    def get(self, request, *args, **kwargs):
        q = request.GET['q']
        results = Cocktail.objects.filter(
            name__contains=q).order_by(Lower("name"))
        if len(results) == 1:
            return redirect("cocktails:detail", results[0].id)
        q = " _ " if q == "" else q
        return render(request, self.template_name, {"cocktails": results, "q": q})


@method_decorator(login_required, name='dispatch')
class ShoppingListView(View):
    template_name = "cocktails/shopping-list.html"
    context_object_name = "items"

    def get(self, request):
        user_ingredients = Ingredient.objects.filter(
            on_shopping_list_of=request.user)
        return render(request, self.template_name,
                      {"items": user_ingredients.order_by(Lower("cocktail"))})

    def post(self, request):
        # get shopping list of logged in user
        shopping_list = Ingredient.objects.filter(
            on_shopping_list_of=request.user)

        for item in request.POST.getlist("on_shopping_list"):
            try:
                key, value = item.split(":")
                ingredient = Ingredient.objects.get(pk=key)
                ingredient.on_shopping_list_of = request.user if value == "True" else None
                ingredient.save()
            except:
                pass
        return redirect("cocktails:shopping-list")


class CocktailsDetailView(DetailView):
    model = Cocktail
    template_name = "cocktails/detail.html"

    def get_context_data(self, **kwargs):
        context = super(CocktailsDetailView, self).get_context_data(**kwargs)
        context["ingredients"] = Ingredient.objects.filter(
            cocktail=self.object.id)
        votes = Cocktail.objects.get(pk=self.object.id).vote_set.all()
        for vote in votes:
            if self.request.user == vote.voter:
                context["votable"] = "up" if vote.is_upvote else "down"
                return context
        return context


class UserProfileView(View):
    template_name = "cocktails/user_profile.html"

    def get(self, request, id):
        return render(request, template_name=self.template_name, context={
            "cocktails": Cocktail.objects.filter(creator=id),
            "other_user": User.objects.filter(pk=id).first()
        })


@method_decorator(login_required, name='dispatch')
class CocktailCreate(CreateView):
    form_class = CocktailForm
    template_name = "cocktails/cocktail_form.html"

    def post(self, request, *args, **kwargs):
        # id = kwargs["pk"]
        form = self.form_class(request.POST, request.FILES)
        if form.is_valid() and form.units_valid(request.POST.getlist("unit")):
            cocktail = form.save(commit=False)
            ingredients = []
            counter = request.POST["ingredient_counter"]
            ingredient_counter = int(counter) if counter else 0
            for idx in range(ingredient_counter):
                ing = Ingredient()
                ing.name = request.POST.getlist("ingredient_name")[idx]
                ing.unit = request.POST.getlist("unit")[idx]
                ing.amount = float(request.POST.getlist("amount")[idx])
                ing.is_alcohol = True if request.POST.getlist(
                    "is_not_alcohol")[idx] == "0" else False
                ing.save()
                ingredients.append(ing)
            cocktail.creator = request.user
            form.save()
            cocktail.ingredient_set.set(ingredients)
            alc_sum = 0
            liq_sum = 0
            ingredient_set = ingredients
            for i in ingredient_set:
                amount = i.amount
                unit = i.unit
                factor = unit.split("l")[0]
                if factor == "m":
                    scale = 0.001
                elif factor == "c":
                    scale = 0.01
                elif factor == "d":
                    scale = 0.1
                else:
                    scale = 1
                amount *= scale
                if i.is_alcohol:
                    alc_sum += amount
                liq_sum += amount
            if liq_sum != 0:
                cocktail.drunk_rating = (alc_sum / liq_sum)
            else:
                cocktail.drunk_rating = 0
            cocktail.save()
            return redirect("cocktails:detail", cocktail.id)

        return render(request, self.template_name, {"form": form})


@method_decorator(login_required, name='dispatch')
class CocktailUpdate(UpdateView):
    model = Cocktail
    fields = ["name", "picture"]

    def get(self, request, *args, **kwargs):
        get = super(CocktailUpdate, self).get(request, args, kwargs)
        return get

    def get_context_data(self, **kwargs):
        context = super(CocktailUpdate, self).get_context_data(**kwargs)
        ingredients = Ingredient.objects.filter(cocktail=self.object.id)
        context.update({"ingredients": ingredients})

        return context

    def get_template_names(self):
        pass


@method_decorator(login_required, name='dispatch')
class CocktailDelete(DeleteView):
    model = Cocktail
    success_url = reverse_lazy("cocktails:index")


class UserFormView(View):
    form_class = UserForm
    template_name = "cocktails/user_form.html"

    def get(self, request):
        form = self.form_class(None)
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = self.form_class(request.POST)
        if "register" in request.POST and form.is_valid():
            # fake, validation commit
            user = form.save(commit=False)

            # cleaned (normalized) data
            username = form.cleaned_data['username']
            password = form.cleaned_data["password"]

            user.set_password(password)
            user.save()
        else:
            username = request.POST["username"]
            password = request.POST["password"]
        # returns User objects if credentials r correct
        user = authenticate(username=username, password=password)

        if user is not None and user.is_active:
            login(request, user)
            return redirect("cocktails:index")
        return render(request, self.template_name, {"form": form})


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect("cocktails:index")


@method_decorator(login_required, name='dispatch')
class VoteView(View):

    def get(self, id):
        return redirect("cocktails:detail", id)

    def post(self, request, id):
        vote = Vote()
        vote.voter = request.user
        vote.is_upvote = True if request.POST["vote"] == "up" else False
        cocktail = Cocktail.objects.get(pk=id)
        vote.cocktail = cocktail
        vote.save()
        total_upvotes = Vote.objects.filter(cocktail=id, is_upvote=True)
        total_downvotes = Vote.objects.filter(cocktail=id, is_upvote=False)
        cocktail.taste_rating = len(total_upvotes) - len(total_downvotes)
        cocktail.save()
        return redirect("cocktails:detail", id)
