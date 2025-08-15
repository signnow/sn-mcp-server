from . import signnow

def register_tools(mcp, cfg):
    signnow.bind(mcp, cfg)