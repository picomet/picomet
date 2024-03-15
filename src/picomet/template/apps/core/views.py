from picomet.decorators import template
from picomet.views import render

# Create your views here.


@template("Index")
def index(request):
    context = {}
    return render(request, context)
