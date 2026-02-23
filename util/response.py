import json


class Response:
    def __init__(self):
        self._status_code = 200
        self._status_text = "OK"
        self._headers = {}
        self._cookies = {}
        self._body = b""
        self._content_type_set = False

    def set_status(self, code, text):
        self._status_code = code
        self._status_text = text
        return self

    def headers(self, headers):
        # Add all headers from the dict
        for key, value in headers.items():
            self._headers[key] = value
            # Track if Content-Type was explicitly set
            if key.lower() == 'content-type':
                self._content_type_set = True
        return self

    def cookies(self, cookies):
        # Add all cookies from the dict
        for key, value in cookies.items():
            self._cookies[key] = value
        return self

    def bytes(self, data):
        # Append bytes to body
        self._body += data
        return self

    def text(self, data):
        # Append text as bytes to body
        self._body += data.encode('utf-8')
        return self

    def json(self, data):
        # Convert to JSON and set as body, overwriting existing content
        json_str = json.dumps(data)
        self._body = json_str.encode('utf-8')
        # Set Content-Type header
        self._headers['Content-Type'] = 'application/json'
        self._content_type_set = True
        return self

    def to_data(self):
        # Build the complete HTTP response
        
        # Status line
        status_line = "HTTP/1.1 " + str(self._status_code) + " " + self._status_text + "\r\n"
        response = status_line.encode("utf-8")
        
        # Add Content-Type if not set
        if not self._content_type_set:
            self._headers['Content-Type'] = 'text/plain; charset=utf-8'
        
        # nosniff header must be set on all responses
        self._headers['X-Content-Type-Options'] = 'nosniff'
        
        # Add Content-Length header
        self._headers['Content-Length'] = str(len(self._body))
        
        # Add all headers
        for key, value in self._headers.items():
            response += f"{key}: {value}\r\n".encode('utf-8')
        
        # Add cookies as Set-Cookie headers
        for key, value in self._cookies.items():
            response += f"Set-Cookie: {key}={value}\r\n".encode('utf-8')
        
        # Empty line to separate headers from body
        response += b'\r\n'
        
        # Add body
        response += self._body
        
        return response


def test1():
    resp = Response()
    resp.text("hello")
    expected = b'HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nX-Content-Type-Options: nosniff\r\nContent-Length: 5\r\n\r\nhello'
    actual = resp.to_data()
    
    assert b'200 OK' in actual
    assert b'Content-Length: 5' in actual
    assert b'hello' in actual
    assert b'X-Content-Type-Options: nosniff' in actual
    print("Test 1 passed")

#status test
def test2():
    resp = Response()
    resp.set_status(404, "Not Found").text("Page not found")
    actual = resp.to_data()
    assert b'404 Not Found' in actual
    assert b'Page not found' in actual
    print("Test 2 passed")


#cookie test
def test3():
    resp = Response()
    resp.cookies({"session": "abc123"}).text("hello")
    actual = resp.to_data()
    assert b'Set-Cookie: session=abc123' in actual
    print("Test 3 passed")

#test json response
def test4():
    resp = Response()
    resp.json({"message": "success"})
    actual = resp.to_data()
    assert b'application/json' in actual
    assert b'{"message": "success"}' in actual
    print("Test 4 passed")


if __name__ == '__main__':
    test1()
    test2()
    test3()
    test4()
    print("All tests passed")