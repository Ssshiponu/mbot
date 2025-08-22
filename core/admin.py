# admin.py
from django.contrib import admin
from django.utils.html import format_html
from .models import Conversation
import json

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    # Fields to display in the list view
    list_display = ('sender_id', 'created_at', 'message_count', 'history_preview')
    
    # Fields to filter by
    list_filter = ('created_at',)
    
    # Fields to search by
    search_fields = ('sender_id',)
    
    # Default ordering
    ordering = ('-created_at',)
    
    # Fields to display in the detail view
    fields = ('sender_id', 'formatted_conversation', 'history', 'created_at')
    
    # Make created_at read-only since it's auto-generated
    readonly_fields = ('created_at', 'formatted_conversation')
    
    def message_count(self, obj):
        """Display the number of messages in the conversation history"""
        try:
            history = json.loads(obj.get_history())
            return len(history) if isinstance(history, list) else 0
        except (json.JSONDecodeError, TypeError):
            return 0
    message_count.short_description = 'Messages'
    
    def history_preview(self, obj):
        """Display a preview of the conversation history"""
        try:
            history = json.loads(obj.get_history())
            if isinstance(history, list) and history:
                # Get the first message content as preview
                first_message = history[0]
                if isinstance(first_message, dict) and 'content' in first_message:
                    role = first_message.get('role', 'unknown')
                    content = first_message.get('content', '')
                    preview = f"{role}: {content}"
                    return (preview[:60] + '...') if len(preview) > 60 else preview
                else:
                    # Fallback for other formats
                    first_message = str(first_message)
                    return (first_message[:50] + '...') if len(first_message) > 50 else first_message
            return "Empty"
        except (json.JSONDecodeError, TypeError):
            return "Invalid JSON"
    history_preview.short_description = 'Conversation Preview'
    
    # Custom actions
    actions = ['clear_history']
    
    def clear_history(self, request, queryset):
        """Custom action to clear conversation history"""
        updated = queryset.update(history="[]")
        self.message_user(request, f'{updated} conversation(s) history cleared.')
    clear_history.short_description = "Clear selected conversations history"
    
    def formatted_conversation(self, obj):
        """Display the full conversation in a table format"""
        try:
            history = json.loads(obj.get_history())
            if isinstance(history, list) and history:
                table_rows = []
                for i, message in enumerate(history, 1):
                    if isinstance(message, dict) and 'role' in message and 'content' in message:
                        role = message['role'].upper()
                        content = message['content']
                        table_rows.append(f"<tr><td>{i}</td><td>{role}</td><td>{content}</td></tr>")
                    else:
                        table_rows.append(f"<tr><td>{i}</td><td>UNKNOWN</td><td>{str(message)}</td></tr>")
                
                table_html = f"""
                <table border="1" cellpadding="5" cellspacing="0">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Role</th>
                            <th>Message</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join(table_rows)}
                    </tbody>
                </table>
                """
                return format_html(table_html)
            return "No messages"
        except (json.JSONDecodeError, TypeError):
            return "Invalid JSON format"
    formatted_conversation.short_description = 'Conversation Table'