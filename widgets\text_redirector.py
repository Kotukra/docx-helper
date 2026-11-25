# widgets/text_redirector.py
class TextRedirector:
    def __init__(self, text_edit):
        self.text_edit = text_edit
    def write(self, string):
        self.text_edit.append(string.rstrip())
    def flush(self):
        pass