import socketserver
import os
import json
import uuid
import html
from util.request import Request
from util.router import Router
from util.response import Response
from util.database import chat_collection


# MIME type mapping - CSS and JS need charset=utf-8
MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.ico': 'image/x-icon',
}


def serve_static_files(request, handler):
    """Serve files from the public directory"""
    file_path = request.path[1:]  # Remove leading slash
    
    # Security: prevent path traversal
    if '..' in file_path:
        response = Response()
        response.set_status(404, "Not Found")
        response.text("File not found")
        handler.request.sendall(response.to_data())
        return
    
    # Check if file exists
    if not os.path.exists(file_path):
        response = Response()
        response.set_status(404, "Not Found")
        response.text("File not found")
        handler.request.sendall(response.to_data())
        return
    
    # Determine MIME type
    _, ext = os.path.splitext(file_path)
    mime_type = MIME_TYPES.get(ext, 'application/octet-stream')
    
    # Read file
    try:
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        response = Response()
        response.headers({'Content-Type': mime_type})
        response.bytes(file_content)
        handler.request.sendall(response.to_data())
    except Exception as e:
        print(f"Error reading file: {e}")
        response = Response()
        response.set_status(500, "Internal Server Error")
        response.text("Error reading file")
        handler.request.sendall(response.to_data())


def render_template(template_name):
    """Render an HTML template with layout"""
    try:
        # Read layout
        with open('public/layout/layout.html', 'r', encoding='utf-8') as f:
            layout = f.read()
        
        # Read page content
        with open(f'public/{template_name}', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace placeholder
        rendered = layout.replace('{{content}}', content)
        return rendered
    except Exception as e:
        print(f"Error rendering template: {e}")
        return "<html><body>Error rendering page</body></html>"


def serve_index(request, handler):
    """Serve the index page"""
    rendered = render_template('index.html')
    response = Response()
    response.headers({'Content-Type': 'text/html; charset=utf-8'})
    response.text(rendered)
    handler.request.sendall(response.to_data())


def serve_chat(request, handler):
    """Serve the chat page"""
    rendered = render_template('chat.html')
    response = Response()
    response.headers({'Content-Type': 'text/html; charset=utf-8'})
    response.text(rendered)
    handler.request.sendall(response.to_data())


def get_or_create_session(request, response):
    """Get or create session cookie"""
    session_id = request.cookies.get('session')
    if not session_id:
        session_id = str(uuid.uuid4())
        response.cookies({'session': session_id})
    return session_id


def create_chat_message(request, handler):
    """POST /api/chats"""
    response = Response()
    session_id = get_or_create_session(request, response)
    
    try:
        body_text = request.body.decode('utf-8')
        data = json.loads(body_text)
        content = data.get('content', '')
        
        # Escape HTML
        content = html.escape(content)
        
        # Create message with reactions field
        message = {
            'id': str(uuid.uuid4()),
            'author': session_id,
            'content': content,
            'updated': False,
            'reactions': {}  # Initialize empty reactions dict
        }
        
        chat_collection.insert_one(message)
        
        response.text("Great work sending a chat message!!")
        handler.request.sendall(response.to_data())
    except Exception as e:
        print(f"Error creating message: {e}")
        response.set_status(500, "Internal Server Error")
        response.text("Error creating message")
        handler.request.sendall(response.to_data())


def get_chat_messages(request, handler):
    """GET /api/chats"""
    try:
        messages = list(chat_collection.find({}))
        
        # Process each message
        for message in messages:
            # Remove MongoDB _id
            if '_id' in message:
                del message['_id']
            
            # Ensure reactions field exists (for old messages)
            if 'reactions' not in message:
                message['reactions'] = {}
        
        response = Response()
        response.json({'messages': messages})
        handler.request.sendall(response.to_data())
    except Exception as e:
        print(f"Error getting messages: {e}")
        response = Response()
        response.set_status(500, "Internal Server Error")
        response.text("Error getting messages")
        handler.request.sendall(response.to_data())


def update_chat_message(request, handler):
    """PATCH /api/chats/{id}"""
    # Extract message ID
    path_parts = request.path.split('/')
    if len(path_parts) < 4:
        response = Response()
        response.set_status(400, "Bad Request")
        response.text("Invalid request")
        handler.request.sendall(response.to_data())
        return
    
    message_id = path_parts[3]
    session_id = request.cookies.get('session')
    
    if not session_id:
        response = Response()
        response.set_status(403, "Forbidden")
        response.text("Forbidden")
        handler.request.sendall(response.to_data())
        return
    
    try:
        # Find message
        message = chat_collection.find_one({'id': message_id})
        
        if not message:
            response = Response()
            response.set_status(404, "Not Found")
            response.text("Message not found")
            handler.request.sendall(response.to_data())
            return
        
        # Check authorization
        if message['author'] != session_id:
            response = Response()
            response.set_status(403, "Forbidden")
            response.text("Forbidden")
            handler.request.sendall(response.to_data())
            return
        
        # Update message
        body_text = request.body.decode('utf-8')
        data = json.loads(body_text)
        new_content = html.escape(data.get('content', ''))
        
        chat_collection.update_one(
            {'id': message_id},
            {'$set': {'content': new_content, 'updated': True}}
        )
        
        response = Response()
        response.text("Message updated")
        handler.request.sendall(response.to_data())
    except Exception as e:
        print(f"Error updating message: {e}")
        response = Response()
        response.set_status(500, "Internal Server Error")
        response.text("Error updating message")
        handler.request.sendall(response.to_data())


def delete_chat_message(request, handler):
    """DELETE /api/chats/{id}"""
    # Extract message ID
    path_parts = request.path.split('/')
    if len(path_parts) < 4:
        response = Response()
        response.set_status(400, "Bad Request")
        response.text("Invalid request")
        handler.request.sendall(response.to_data())
        return
    
    message_id = path_parts[3]
    session_id = request.cookies.get('session')
    
    if not session_id:
        response = Response()
        response.set_status(403, "Forbidden")
        response.text("Forbidden")
        handler.request.sendall(response.to_data())
        return
    
    try:
        # Find message
        message = chat_collection.find_one({'id': message_id})
        
        if not message:
            response = Response()
            response.set_status(404, "Not Found")
            response.text("Message not found")
            handler.request.sendall(response.to_data())
            return
        
        # Check authorization
        if message['author'] != session_id:
            response = Response()
            response.set_status(403, "Forbidden")
            response.text("Forbidden")
            handler.request.sendall(response.to_data())
            return
        
        # Delete message
        chat_collection.delete_one({'id': message_id})
        
        response = Response()
        response.text("Message deleted")
        handler.request.sendall(response.to_data())
    except Exception as e:
        print(f"Error deleting message: {e}")
        response = Response()
        response.set_status(500, "Internal Server Error")
        response.text("Error deleting message")
        handler.request.sendall(response.to_data())


def add_emoji_reaction(request, handler):
    """PATCH /api/reaction/{messageID} - Add emoji reaction"""
    # Extract message ID from path
    path_parts = request.path.split('/')
    if len(path_parts) < 4:
        response = Response()
        response.set_status(400, "Bad Request")
        response.text("Invalid request")
        handler.request.sendall(response.to_data())
        return
    
    message_id = path_parts[3]
    session_id = request.cookies.get('session')
    
    if not session_id:
        response = Response()
        response.set_status(403, "Forbidden")
        response.text("Must be logged in")
        handler.request.sendall(response.to_data())
        return
    
    try:
        # Parse emoji from request body
        body_text = request.body.decode('utf-8')
        data = json.loads(body_text)
        emoji = data.get('emoji', '')
        
        if not emoji:
            response = Response()
            response.set_status(400, "Bad Request")
            response.text("Emoji required")
            handler.request.sendall(response.to_data())
            return
        
        # Find the message
        message = chat_collection.find_one({'id': message_id})
        
        if not message:
            response = Response()
            response.set_status(404, "Not Found")
            response.text("Message not found")
            handler.request.sendall(response.to_data())
            return
        
        # Get current reactions (handle old messages without reactions field)
        reactions = message.get('reactions', {})
        
        # Check if user already reacted with this emoji
        if emoji in reactions and session_id in reactions[emoji]:
            response = Response()
            response.set_status(403, "Forbidden")
            response.text("Already reacted with this emoji")
            handler.request.sendall(response.to_data())
            return
        
        # Add the reaction
        if emoji not in reactions:
            reactions[emoji] = []
        reactions[emoji].append(session_id)
        
        # Update in database
        chat_collection.update_one(
            {'id': message_id},
            {'$set': {'reactions': reactions}}
        )
        
        response = Response()
        response.text("Reaction added")
        handler.request.sendall(response.to_data())
        
    except Exception as e:
        print(f"Error adding reaction: {e}")
        response = Response()
        response.set_status(500, "Internal Server Error")
        response.text("Error adding reaction")
        handler.request.sendall(response.to_data())


def remove_emoji_reaction(request, handler):
    """DELETE /api/reaction/{messageID} - Remove emoji reaction"""
    # Extract message ID from path
    path_parts = request.path.split('/')
    if len(path_parts) < 4:
        response = Response()
        response.set_status(400, "Bad Request")
        response.text("Invalid request")
        handler.request.sendall(response.to_data())
        return
    
    message_id = path_parts[3]
    session_id = request.cookies.get('session')
    
    if not session_id:
        response = Response()
        response.set_status(403, "Forbidden")
        response.text("Must be logged in")
        handler.request.sendall(response.to_data())
        return
    
    try:
        # Parse emoji from request body
        body_text = request.body.decode('utf-8')
        data = json.loads(body_text)
        emoji = data.get('emoji', '')
        
        if not emoji:
            response = Response()
            response.set_status(400, "Bad Request")
            response.text("Emoji required")
            handler.request.sendall(response.to_data())
            return
        
        # Find the message
        message = chat_collection.find_one({'id': message_id})
        
        if not message:
            response = Response()
            response.set_status(404, "Not Found")
            response.text("Message not found")
            handler.request.sendall(response.to_data())
            return
        
        # Get current reactions
        reactions = message.get('reactions', {})
        
        # Check if user has this reaction
        if emoji not in reactions or session_id not in reactions[emoji]:
            response = Response()
            response.set_status(403, "Forbidden")
            response.text("You don't have this reaction")
            handler.request.sendall(response.to_data())
            return
        
        # Remove the reaction
        reactions[emoji].remove(session_id)
        
        # Remove emoji key if no more users have this reaction
        if len(reactions[emoji]) == 0:
            del reactions[emoji]
        
        # Update in database
        chat_collection.update_one(
            {'id': message_id},
            {'$set': {'reactions': reactions}}
        )
        
        response = Response()
        response.text("Reaction removed")
        handler.request.sendall(response.to_data())
        
    except Exception as e:
        print(f"Error removing reaction: {e}")
        response = Response()
        response.set_status(500, "Internal Server Error")
        response.text("Error removing reaction")
        handler.request.sendall(response.to_data())


class MyTCPHandler(socketserver.BaseRequestHandler):

    def __init__(self, request, client_address, server):
        self.router = Router()
        
        # Page routes
        self.router.add_route("GET", "/", serve_index, True)
        self.router.add_route("GET", "/chat", serve_chat, True)
        self.router.add_route("GET", "/public/", serve_static_files, False)
        
        # Chat API routes
        self.router.add_route("POST", "/api/chats", create_chat_message, True)
        self.router.add_route("GET", "/api/chats", get_chat_messages, True)
        self.router.add_route("PATCH", "/api/chats/", update_chat_message, False)
        self.router.add_route("DELETE", "/api/chats/", delete_chat_message, False)
        
        # AO1: Emoji Reaction routes
        self.router.add_route("PATCH", "/api/reaction/", add_emoji_reaction, False)
        self.router.add_route("DELETE", "/api/reaction/", remove_emoji_reaction, False)
        
        super().__init__(request, client_address, server)

    def handle(self):
        received_data = self.request.recv(2048)
        print(self.client_address)
        print("--- received data ---")
        print(received_data)
        print("--- end of data ---\n\n")
        request = Request(received_data)

        self.router.route_request(request, self)


def main():
    host = "0.0.0.0"
    port = 8080
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    server = socketserver.ThreadingTCPServer((host, port), MyTCPHandler)

    print("Listening on port " + str(port))
    server.serve_forever()


if __name__ == "__main__":
    main()