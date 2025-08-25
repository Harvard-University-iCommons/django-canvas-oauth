from django.contrib import admin

from canvas_oauth.models import CanvasOAuth2Token


@admin.register(CanvasOAuth2Token)
class CanvasOAuth2TokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'canvas_domain', 'expires', 'created_on', 'updated_on')
    list_filter = ('canvas_domain', 'created_on')
    search_fields = ('user__username', 'user__email', 'canvas_domain')
    readonly_fields = ('created_on', 'updated_on')

    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing token
            return self.readonly_fields + ('user', 'canvas_domain')
        return self.readonly_fields
