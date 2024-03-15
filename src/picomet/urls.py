from django.conf import settings
from django.conf.urls.static import static

from picomet.parser import ASSET_URL

urlpatterns = []
urlpatterns += static(
    f"/{ASSET_URL}", document_root=settings.BASE_DIR / ".picomet/cache/assets"
)
