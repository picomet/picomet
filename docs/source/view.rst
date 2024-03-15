View
====

First of all, create a comet template:

.. code-block:: text

  <!-- apps/core/comets/pages/New.html -->
  <div>
    {$ variable $}
  </div>

Learn more about :doc:`/comet` template.

Define a view:

.. code-block:: python

  # apps/core/views.py
  from picomet.decorators import template
  from picomet.views import render

  @template("pages/New")
  def new(request):
      context = {"variable": "hello world"}
      return render(request, context)


Configure url:

.. code-block:: python

  # apps/core/urls.py
  from django.urls import path

  from core import views

  app_name = "core"

  urlpatterns = [
      path("new", views.new, name="new"),
  ]
