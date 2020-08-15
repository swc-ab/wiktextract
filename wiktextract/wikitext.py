# Simple WikiMedia markup (WikiText) syntax parser
#
# Copyright (c) 2020 Tatu Ylonen.  See file LICENSE and https://ylonen.org

import re
import enum


# HTML tags that are allowed in input.  These are generated as HTML nodes
# to distinguish them from text.  Note that only the tags themselves are
# made HTML nodes to distinguisth them from plain text ("<" in returned plain
# text should be rendered as "&lt;" in HTML).  This does not try to match
# HTML start tags against HTML end tags, and only the tag itself is included
# as children of HTML nodes.
ALLOWED_HTML_TAGS = set([
    "H1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "abbr", "b", "bdi", "bdo", "blockquote", "cite", "code", "data", "del",
    "dfn", "em", "i", "ins", "kbd", "nark", "q", "rp", "rt", "ruby",
    "s", "samp", "small", "strong", "sub", "sup", "time", "u", "var", "wbr",
    "dl", "dt", "dd",
    "ol", "ul", "li",
    "div", "span",
    "table", "td", "tr", "th", "caption", "thead", "tfoot", "tbody",
    "center", "font", "rb", "strike", "tt",
    "onlyinclude", "noinclude", "includeonly",
    "math", "gallery", "ref",
])

# MediaWiki magic words.  See https://www.mediawiki.org/wiki/Help:Magic_words
MAGIC_WORDS = set([
    "__NOTOC__",
    "__FORCETOC__",
    "__TOC__",
    "__NOEDITSECTION__",
    "__NEWSECTIONLINK__",
    "__NONEWSECTIONLINK__",
    "__NOGALLERY__",
    "__HIDDENCAT__",
    "__EXPECTUNUSEDCATEGORY__",
    "__NOCONTENTCONVERT__",
    "__NOCC__",
    "__NOTITLECONVERT__",
    "__NOTC__",
    "__START__",
    "__END__",
    "__INDEX__",
    "__NOINDEX__",
    "__STATICREDIRECT__",
    "__NOGLOBAL__",
    "__DISAMBIG__",
])

# This list should include names of predefined parser functions and
# predefined variables (some of which can take arguments using the same
# syntax as parser functions and we treat them as parser functions).
# See https://en.wikipedia.org/wiki/Help:Magic_words#Parser_functions
PARSER_FUNCTIONS = set([
    "FULLPAGENAME",
    "PAGENAME",
    "BASEPAGENAME",
    "ROOTPAGENAME",
    "SUBPAGENAME",
    "ARTICLEPAGENAME",
    "SUBJECTPAGENAME",
    "TALKPAGENAME",
    "NAMESPACENUMBER",
    "NAMESPACE",
    "ARTICLESPACE",
    "SUBJECTSPACE",
    "TALKSPACE",
    "FULLPAGENAMEE",
    "PAGENAMEE",
    "BASEPAGENAMEE",
    "ROOTPAGENAMEE",
    "SUBPAGENAMEE",
    "ARTICLEPAGENAMEE",
    "SUBJECTPAGENAMEE",
    "TALKPAGENAMEE",
    "NAMESPACENUMBERE",
    "NAMESPACEE",
    "ARTICLESPACEE",
    "SUBJECTSPACEE",
    "TALKSPACEE",
    "SHORTDESC",
    "SITENAME",
    "SERVER",
    "SERVERNAME",
    "SCRIPTPATH",
    "CURRENTVERSION",
    "CURRENTYEAR",
    "CURRENTMONTH",
    "CURRENTMONTHNAME",
    "CURRENTMONTHABBREV",
    "CURRENTDAY",
    "CURRENTDAY2",
    "CUEEWNTDOW",
    "CURRENTDAYNAME",
    "CURRENTTIME",
    "CURRENTHOUR",
    "CURRENTWEEK",
    "CURRENTTIMESTAMP",
    "LOCALYEAR",
    "LOCALMONTH",
    "LOCALMONTHNAME",
    "LOCALMONTHABBREV",
    "LOCALDAY",
    "LOCALDAY2",
    "LOCALDOW",
    "LOCALDAYNAME",
    "LOCALTIME",
    "LOCALHOUR",
    "LOCALWEEK",
    "LOCALTIMESTAMP",
    "REVISIONDAY",
    "REVISIONDAY2",
    "REVISIONMONTH",
    "REVISIONYEAR",
    "REVISIONTIMESTAMP",
    "REVISIONUSER",
    "NUMBEROFPAGES",
    "NUMBEROFARTICLES",
    "NUMBEROFFILES",
    "NUMBEROFEDITS",
    "NUMBEROFUSERS",
    "NUMBEROFADMINS",
    "NUMBEROFACTIVEUSERS",
    "PAGEID",
    "PAGESIZE",
    "PROTECTIONLEVEL",
    "PROTECTIONEXPIRY",
    "PENDINGCHANGELEVEL",
    "PAGESINCATEGORY",
    "NUMBERINGROUP",
    "lc",
    "lcfirst",
    "uc",
    "ucfirst",
    "formatnum",
    "#dateformat",
    "formatdate",
    "padleft",
    "padright",
    "plural",
    "#time",
    "#timel",
    "gender",
    "#tag",
    "localurl",
    "fullurl",
    "canonicalurl",
    "filepath",
    "urlencode",
    "anchorencode",
    "ns",
    "nse",
    "#rel2abs",
    "#titleparts",
    "#expr",
    "#if",
    "#ifeq",
    "#iferror",
    "#ifexpr",
    "#ifexist",
    "#switch",
    "#babel",
    "#categorytree",
    "#coordinates",
    "#invoke",
    "#language",
    "#lst",
    "#lsth",
    "#lstx",
    "#property",
    "#related",
    "#section",
    "#section-h",
    "#section-x",
    "#statements",
    "#target",
])


@enum.unique
class NodeKind(enum.Enum):
    # Root node of the tree.  This represents the parsed document.
    # Its arguments are [pagetitle].
    ROOT = enum.auto(),

    # Level2 subtitle.  Arguments are the title, children are what the section
    # contains.
    LEVEL2 = enum.auto(),

    # Level3 subtitle
    LEVEL3 = enum.auto(),

    # Level4 subtitle
    LEVEL4 = enum.auto(),

    # Level5 subtitle
    LEVEL5 = enum.auto(),

    # Level6 subtitle
    LEVEL6 = enum.auto(),

    # Content to be rendered in italic.  Content is in children.
    ITALIC = enum.auto(),

    # Content to be rendered in bold.  Content is in children.
    BOLD = enum.auto(),

    # Horizontal line.  No arguments or children.
    HLINE = enum.auto(),

    # A list item.  Nested items will be in children.  Items on the same
    # level will be on the same level.  There is no explicit node for a list.
    # Args is directly the token for this item (not as a list).  Children
    # is what goes in this list item.
    LIST_ITEM = enum.auto(),  # args = token for this item

    # Preformatted text were markup is interpreted.  Content is in children.
    # Indicated in WikiText by starting lines with a space.
    PREFORMATTED = enum.auto(),  # Preformatted inline text

    # Preformatted text where markup is NOT interpreted.  Content is in
    # children. Indicated in WikiText by <pre>...</pre>.
    PRE = enum.auto(),  # Preformatted text where specials not interpreted

    # HTML tag (open or close tag).  Args is the name of the tag
    # directly (i.e., not a list).  Attrs contains tag attributes and
    # "_close" with value True if this is a close tag.  It contains
    # "_also_close" with value True if this is an open tag with a
    # slash at the end of the tag.  The special tags <onlyinclude>,
    # <noinclude>, and <includeonly> also generate this tag.  Children
    # of HTML nodes are not used.
    HTML = enum.auto(),

    # An internal Wikimedia link (marked with [[...]]).  The link arguments
    # are in args.  This tag is also used for media inclusion.  Links with
    # trailing word end immediately after the link have the trailing part
    # in link children.
    LINK = enum.auto(),

    # A template call (transclusion).  Template name is in first argument
    # and template arguments in subsequent args.  Children are not used.
    # In WikiText {{name|arg1|...}}.
    TEMPLATE = enum.auto(),

    # A template argument expansion.  Variable name is in first argument and
    # subsequent arguments in remaining arguments.  Children are not used.
    # In WikiText {{{name|...}}}
    TEMPLATEVAR = enum.auto(),

    # A parser function invocation.  This is also used for built-in
    # variables such as {{PAGENAME}}.  Parser function name is in
    # first argument and subsequent arguments are its parameters.
    # Children are not used.  In WikiText {{name:arg1|arg2|...}}.
    PARSERFN = enum.auto(),

    # An external URL.  The first argument is the URL.  The second optional
    # argument is the display text. Children are not used.
    URL = enum.auto(),

    # A table.  Content is in children.
    TABLE = enum.auto(),

    # A table caption (under TABLE).  Content is in children.
    TABLE_CAPTION = enum.auto(),

    # A table header row (under TABLE).  Content is in children.
    TABLE_HEADER_ROW = enum.auto(),

    # A table header cell (under TABLE_HEADER_ROW).  Content is in children.
    TABLE_HEADER_CELL = enum.auto(),

    # A table row (under TABLE).  Content is in children.
    TABLE_ROW = enum.auto(),

    # A table cell (under TABLE_ROW).  Content is in children.
    TABLE_CELL = enum.auto(),

    # A MediaWiki magic word.  The magic word is assigned directly to args
    # (not as a list).  Children are not used.
    MAGIC_WORD = enum.auto(),

    # XXX <ref ...> and <references />
    # XXX -{ ... }- syntax, see

    # XXX __NOTOC__


HAVE_ARGS_KINDS = (
    NodeKind.LINK,
    NodeKind.TEMPLATE,
    NodeKind.TEMPLATEVAR,
    NodeKind.PARSERFN,
    NodeKind.URL,
)


# Node kinds that generate an error if they have not been properly closed.
MUST_CLOSE_KINDS = (
    NodeKind.ITALIC,
    NodeKind.BOLD,
    NodeKind.PRE,
    NodeKind.HTML,
    NodeKind.LINK,
    NodeKind.TEMPLATE,
    NodeKind.TEMPLATEVAR,
    NodeKind.PARSERFN,
    NodeKind.URL,
    NodeKind.TABLE,
)

# Node kinds that are automatically closed at a newline
CLOSE_AT_NEWLINE_KINDS = (
    NodeKind.PREFORMATTED,
    NodeKind.LIST_ITEM,
)

class WikiNode(object):
    """Node in the parse tree for WikiMedia text."""
    __slots__ = (
        "kind",
        "args",
        "attrs",
        "children",
        "loc",
    )

    def __init__(self, kind, loc):
        assert isinstance(kind, NodeKind)
        assert isinstance(loc, int)
        self.kind = kind
        self.args = []  # List of lists
        self.attrs = {}
        self.children = []   # list of str and WikiNode
        self.loc = loc

    def __str__(self):
        return "<{}({}) {}>".format(self.kind.name,
                                    self.args if isinstance(self.args, str)
                                    else ", ".join(map(repr, self.args)),
                                    ", ".join(map(repr, self.children)))

    def __repr__(self):
        return self.__str__()


class ParseCtx(object):
    """Parsing context for parsing WikiMedia text.  This contains the parser
    stack, which also implicitly contains all text parsed so far and the
    partial parse tree."""
    __slots__ = (
        "stack",
        "linenum",
        "beginning_of_line",
        "errors",
        "pagetitle",
        "nowiki",
        "suppress_special",
    )

    def __init__(self, pagetitle):
        assert isinstance(pagetitle, str)
        node = WikiNode(NodeKind.ROOT, 0)
        node.args.append(pagetitle)
        self.stack = [node]
        self.linenum = 1
        self.beginning_of_line = True
        self.errors = []
        self.pagetitle = pagetitle
        self.nowiki = False
        self.suppress_special = False

    def push(self, kind):
        assert isinstance(kind, NodeKind)
        node = WikiNode(kind, self.linenum)
        prev = self.stack[-1]
        prev.children.append(node)
        self.stack.append(node)
        self.suppress_special = False
        return node

    def pop(self, warn_unclosed):
        """Pops a node from the stack.  If the node has arguments, this moves
        remaining children of the node into its arguments.  If ``warn_unclosed``
        is True, this warns about nodes that should be explicitly closed
        not having been closed."""
        assert warn_unclosed in (True, False)
        node = self.stack[-1]

        # When popping BOLD and ITALIC nodes, if the node has no children,
        # just remove the node from it's parent's children.  We may otherwise
        # generate spurious empty BOLD and ITALIC nodes when closing them
        # out-of-order (which happens always with '''''bolditalic''''').
        if node.kind in (NodeKind.BOLD, NodeKind.ITALIC) and not node.children:
            self.stack.pop()
            assert self.stack[-1].children[-1].kind == node.kind
            self.stack[-1].children.pop()
            return

        # If the node has arguments, move remamining children to be the last
        # argument
        if node.kind in HAVE_ARGS_KINDS:
            node.args.append(node.children)
            node.children = []
        if warn_unclosed and node.kind in MUST_CLOSE_KINDS:
            self.error("format {} not properly closed, started on line {}"
                       "".format(node.kind.name, node.loc))

        # When popping a TEMPLATE, check if its name is a constant that
        # is a known parser function (including predefined variable).
        # If so, turn this node into a PARSERFN node.
        if (node.kind == NodeKind.TEMPLATE and node.args and
            len(node.args[0]) == 1 and isinstance(node.args[0][0], str) and
            node.args[0][0] in PARSER_FUNCTIONS):
            # Change node type to PARSERFN.  Otherwise it has identical
            # structure to a TEMPLATE.
            node.kind = NodeKind.PARSERFN

        self.stack.pop()

    def have(self, kind):
        """Returns True if any node on the stack is of the given kind."""
        assert isinstance(kind, NodeKind)
        for node in self.stack:
            if node.kind == kind:
                return True
        return False

    def error(self, msg, loc=None):
        """Prints a parsing error message and records it in self.errors."""
        if loc is None:
            loc = self.linenum
        msg = "{}:{}: ERROR: {}".format(self.pagetitle, loc, msg)
        print(msg)
        self.errors.append(msg)


def text_fn(ctx, text):
    # Some nodes are automatically popped on newline/text
    if ctx.beginning_of_line and not ctx.nowiki:
        node = ctx.stack[-1]
        if node.kind == NodeKind.LIST_ITEM:
            if (node.children and isinstance(node.children[-1], str) and
                node.children[-1].endswith("\n")):
                ctx.pop(False)
        elif node.kind == NodeKind.PREFORMATTED:
            if (node.children and isinstance(node.children[-1], str) and
                node.children[-1].endswith("\n") and
                not text.startswith(" ") and not text.isspace()):
                ctx.pop(False)

    # If the previous child was a link that doesn't yet have children,
    # and the text to be added starts with valid word characters, assume they
    # are link trail and add them as a child of the link.
    node = ctx.stack[-1]
    if (node.children and isinstance(node.children[-1], WikiNode) and
        node.children[-1].kind == NodeKind.LINK and
        not node.children[-1].children and
        not ctx.suppress_special):
        m = re.match(r"(?s)(\w+)(.*)", text)
        if m:
            node.children[-1].children.append(m.group(1))
            text = m.group(2)
            if not text:
                return

    # If the previous child was also text, merge this additional text with it
    if node.children:
        prev = node.children[-1]
        if isinstance(prev, str):
            # XXX this can result in O(N^2) complexity for long texts.  Change
            # to do the merging in ctx.push() and ctx.pop() using "".join(...)
            # for a whole sequence of strings.
            node.children[-1] = prev + text
            return

    # Add a text child
    node.children.append(text)

def hline_fn(ctx, token):
    ctx.push(NodeKind.HLINE)
    ctx.pop(True)

# Maps subtitle token to its kind
subtitle_to_kind = {
    "==": NodeKind.LEVEL2,
    "===": NodeKind.LEVEL3,
    "====": NodeKind.LEVEL4,
    "=====": NodeKind.LEVEL5,
    "======": NodeKind.LEVEL6,
}

# Maps subtitle node kind to its level.  Keys include all title/subtitle nodes.
kind_to_level = { v: len(k) for k, v in subtitle_to_kind.items() }
kind_to_level[NodeKind.ROOT] = 1

def subtitle_start_fn(ctx, token):
    assert isinstance(ctx, ParseCtx)
    assert isinstance(token, str)
    kind = subtitle_to_kind[token[1:]]
    level = kind_to_level[kind]

    # Keep popping subtitles and other formats until the next subtitle
    # is of a higher level.
    while True:
        node = ctx.stack[-1]
        if kind_to_level.get(node.kind, 99) < level:
            break
        ctx.pop(True)

    # Push the subtitle node.  Subtitle start nodes are guaranteed to have
    # a close node, though the close node could have an incorrect level.
    ctx.push(kind)

def subtitle_end_fn(ctx, token):
    assert isinstance(ctx, ParseCtx)
    assert isinstance(token, str)
    kind = subtitle_to_kind[token[1:]]

    # Keep popping formats until we get to the subtitle node
    while True:
        node = ctx.stack[-1]
        if node.kind in kind_to_level:
            break
        ctx.pop(True)

    # Move children of the subtitle node to be its first argument.
    node = ctx.stack[-1]
    if node.kind != kind:
        ctx.error("subtitle start and end markers level mismatch")
    node.args.append(node.children)
    node.children = []

def italic_fn(ctx, token):
    if not ctx.have(NodeKind.ITALIC):
        # Push new formatting node
        ctx.push(NodeKind.ITALIC)
        return

    # Pop the italic.  If there is an intervening BOLD, push it afterwards
    # to allow closing them in either order.
    push_bold = False
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.ITALIC:
            ctx.pop(False)
            break
        if node.kind == NodeKind.BOLD:
            push_bold = True
        ctx.pop(False)
    if push_bold:
        ctx.push(NodeKind.BOLD)

def bold_fn(ctx, token):
    if not ctx.have(NodeKind.BOLD):
        # Push new formatting node
        ctx.push(NodeKind.BOLD)
        return

    # Pop the bold.  If there is an intervening ITALIC, push it afterwards
    # to allow closing them in either order.
    push_italic = False
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.BOLD:
            ctx.pop(False)
            break
        if node.kind == NodeKind.ITALIC:
            push_italic = True
        ctx.pop(False)
    if push_italic:
        ctx.push(NodeKind.ITALIC)

def ilink_start_fn(ctx, token):
    ctx.push(NodeKind.LINK)

def ilink_end_fn(ctx, token):
    if not ctx.have(NodeKind.LINK):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.LINK:
            ctx.pop(False)
            break
        if node.kind in kind_to_level:
            break  # Never pop past section header
        ctx.pop(True)

def elink_start_fn(ctx, token):
    ctx.push(NodeKind.URL)

def elink_end_fn(ctx, token):
    if not ctx.have(NodeKind.URL):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.URL:
            ctx.pop(False)
            break
        if node.kind in kind_to_level:
            break  # Never pop past section header
        ctx.pop(True)

def url_fn(ctx, token):
    node = ctx.stack[-1]
    if node.kind == NodeKind.URL:
        text_fn(ctx, token)
        return
    node = ctx.push(NodeKind.URL)
    text_fn(ctx, token)
    ctx.pop(False)

def templarg_start_fn(ctx, token):
    """Handler for template argument reference start token {{{."""
    ctx.push(NodeKind.TEMPLATEVAR)


def templarg_end_fn(ctx, token):
    """Handler for template argument reference end token }}}."""
    if not ctx.have(NodeKind.TEMPLATEVAR):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.TEMPLATEVAR:
            ctx.pop(False)
            break
        if node.kind in kind_to_level:
            break  # Never pop past section header
        ctx.pop(True)


def templ_start_fn(ctx, token):
    """Handler for template start token {{."""
    ctx.push(NodeKind.TEMPLATE)


def templ_end_fn(ctx, token):
    """Handler function for template end token }}."""
    if not ctx.have(NodeKind.TEMPLATE) and not ctx.have(NodeKind.PARSERFN):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind in (NodeKind.TEMPLATE, NodeKind.PARSERFN):
            ctx.pop(False)
            break
        if node.kind in kind_to_level:
            break  # Never pop past section header
        ctx.pop(True)


def colon_fn(ctx, token):
    """Handler for a special colon (:) within a template call.  This indicates
    that it is actually a parser function call."""
    node = ctx.stack[-1]

    # Unless we are in the first argument of a template, treat a colon that is
    # not at the beginning of a
    if (node.kind != NodeKind.TEMPLATE or node.args or
        len(node.children) != 1 or not isinstance(node.children[0], str) or
        node.children[0] not in PARSER_FUNCTIONS):
        text_fn(ctx, token)
        return

    # Colon in the first argument of {{name:...}} turns it into a parser
    # function call.
    node.kind = NodeKind.PARSERFN
    node.args.append(node.children)
    node.children = []


def table_start_fn(ctx, token):
    """Handler for table start token {|."""
    ctx.push(NodeKind.TABLE)


def table_caption_fn(ctx, token):
    """Handler for table caption token |+."""
    if not ctx.have(NodeKind.TABLE):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.TABLE:
            break
        ctx.pop(True)
    ctx.push(NodeKind.TABLE_CAPTION)


def table_hdr_cell_fn(ctx, token):
    """Handler function for table header row cell separator ! or !!."""
    print("HDR_CELL_FN", token)
    if not ctx.have(NodeKind.TABLE):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.TABLE_HEADER_ROW:
            ctx.push(NodeKind.TABLE_HEADER_CELL)
            return
        if node.kind == NodeKind.TABLE:
            ctx.push(NodeKind.TABLE_HEADER_ROW)
            ctx.push(NodeKind.TABLE_HEADER_CELL)
            return
        if node.kind == NodeKind.TABLE_CAPTION:
            if ctx.beginning_of_line:
                ctx.pop(False)
                ctx.push(NodeKind.TABLE_HEADER_ROW)
                ctx.push(NodeKind.TABLE_HEADER_CELL)
            else:
                text_fn(ctx, token)
            return
        if node.kind in (NodeKind.TABLE_CELL, NodeKind.TABLE_ROW):
            text_fn(ctx, token)
            return
        ctx.pop(True)


def table_row_fn(ctx, token):
    """Handler function for table row separator |-."""
    if not ctx.have(NodeKind.TABLE):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.TABLE:
            break
        ctx.pop(True)
    ctx.push(NodeKind.TABLE_ROW)


def table_row_cell_fn(ctx, token):
    """Handler function for table row cell separator."""
    if not ctx.have(NodeKind.TABLE):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.TABLE_ROW:
            break
        if node.kind == NodeKind.TABLE:
            ctx.push(NodeKind.TABLE_ROW)
            break
        if node.kind in (NodeKind.TABLE_HEADER_ROW, NodeKind.TABLE_HEADER_CELL,
                         NodeKind.TABLE_CAPTION):
            text_fn(ctx, token)
            return
        ctx.pop(True)
    ctx.push(NodeKind.TABLE_CELL)


def whitespace_fn(ctx, token):
    """Handler function for whitespaces.  Spaces are special in certain
    contexts, such as inside external link syntax [url text], where
    they separate the URL form the display text.  Otherwise spaces are
    treated as normal text.  Note that this puts each word of
    multi-word display text in its own argument.  Spaces at the start of a
    line indicate preformatted text."""
    node = ctx.stack[-1]

    # Spaces at the beginning of a line indicate preformatted text
    if ctx.beginning_of_line and token == " ":
        if node.kind != NodeKind.PREFORMATTED:
            ctx.push(NodeKind.PREFORMATTED)
        text_fn(ctx, token)
        return

    # Spaces inside an external link divide its first argument from its
    # second argument.  All remaining words go into the second argument.
    if node.kind == NodeKind.URL and not node.args:
        node.args.append(node.children)
        node.children = []
        return

    # Otherwise just treat it as plain text.
    text_fn(ctx, token)


def vbar_fn(ctx, token):
    """Handler function for vertical bar |.  The interpretation of
    the vertical bar depends on context; it can separate arguments to
    templates, template argument references, links, etc, and it can
    also separate table row cells."""
    node = ctx.stack[-1]
    if node.kind in HAVE_ARGS_KINDS:
        node.args.append(node.children)
        node.children = []
        return

    if ctx.beginning_of_line:
        table_row_cell_fn(ctx, token)
        return

    text_fn(ctx, token)


def double_vbar_fn(ctx, token):
    """Handle function for double vertical bar ||.  This is used as a column
    separator in tables.  If it occurs in other contexts, it should be
    interpreted as two vertical bars."""
    node = ctx.stack[-1]
    if node.kind in HAVE_ARGS_KINDS:
        vbar_fn(ctx, "|")
        vbar_fn(ctx, "|")
        return

    table_row_cell_fn(ctx, token)


def table_end_fn(ctx, token):
    """Handler function for end of a table token |}."""
    if not ctx.have(NodeKind.TABLE):
        text_fn(ctx, token)
        return
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.TABLE:
            ctx.pop(False)
            break
        if node.kind in kind_to_level:
            break  # Always break before section headers
        ctx.pop(True)


def list_fn(ctx, token):
    """Handles various tokens that start unordered or ordered list items,
    description list items, or indented lines."""
    token = token.strip()
    node = ctx.stack[-1]

    # A colon inside a template means it is a parser function call.  We use
    # colon_fn() to handle that kind of colon.
    if token == ":" and node.kind == NodeKind.TEMPLATE:
        colon_fn(ctx, token)
        return

    # Colons can occur inside links and don't mean a list item
    if node.kind in (NodeKind.LINK, NodeKind.URL):
        text_fn(ctx, token)
        return

    # List items must start a new line; otherwise treat as text
    if not ctx.beginning_of_line:
        text_fn(ctx, token)
        return

    # Pop any lower-level list items
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.LIST_ITEM and len(node.args) < len(token):
            break
        if node.kind in kind_to_level:
            break  # Always break before section header
        if node.kind in (NodeKind.HTML, NodeKind.TEMPLATE,
                         NodeKind.TEMPLATEVAR, NodeKind.PARSERFN,
                         NodeKind.TABLE,
                         NodeKind.TABLE_HEADER_ROW,
                         NodeKind.TABLE_HEADER_CELL,
                         NodeKind.TABLE_ROW,
                         NodeKind.TABLE_CELL):
            break
        ctx.pop(True)
    node = ctx.push(NodeKind.LIST_ITEM)
    node.args = token


def tag_add_attrs(node, attrs, also_end):
    assert isinstance(node, WikiNode)
    assert isinstance(attrs, str)
    assert also_end in (True, False)

    # Set _also_close if needed
    if also_end:
        node.attrs["_also_close"] = True

    # Extract attributes from the tag into the node.attrs dictionary
    for m in re.finditer(r"""(?si)\b([^"'>/=\0-\037\s]+)"""
                        r"""(=("[^"]*"|'[^']*'|[^"'<>`\s]*))?\s*""",
                         attrs):
        name = m.group(1)
        value = m.group(3) or ""
        if value.startswith("'") or value.startswith('"'):
            value = value[1:-1]
        node.attrs[name] = value


def tag_fn(ctx, token):
    """Handler function for tokens that look like HTML tags and their end
    tags.  This includes various built-in tags that aren't actually
    HTML, including <nowiki>."""

    # If it is a HTML comment, just drop it
    if token.startswith("<!"):
        return

    # Try to parse it as a start tag
    m = re.match(r"""<\s*([-a-zA-Z0-9]+)\s*((\b[-a-z0-9]+(=("[^"]*"|"""
                 r"""'[^']*'|[^ \t\n"'`=<>]*))?\s*)*)(/?)\s*>""", token)
    if m:
        # This is a start tag
        name = m.group(1)
        attrs = m.group(2)
        also_end = m.group(6) == "/"
        name = name.lower()
        # Handle <nowiki> start tag
        if name == "nowiki":
            if also_end:
                # Cause certain behaviors to be suppressed, particularly
                # link trail processing.  This will be automatically reset
                # when the next child is inserted in ctx.push().
                ctx.suppress_special = True
            else:
                ctx.nowiki = True
            return

        # Handle <pre> start tag
        if name == "pre":
            node = ctx.push(NodeKind.PRE)
            tag_add_attrs(node, attrs, also_end)
            if also_end:
                ctx.pop(False)
            return

        # Generate error from tags that are not allowed HTML tags
        if name not in ALLOWED_HTML_TAGS:
            ctx.error("html tag <{}> not allowed in WikiText"
                      "".format(name))
            text_fn(ctx, token)
            return

        # Handle other start tag.  We push HTML tags as HTML nodes.
        node = ctx.push(NodeKind.HTML)
        node.args = name
        tag_add_attrs(node, attrs, also_end)

        # Pop it immediately, as we don't store anything other than the
        # tag itself under a HTML tag.
        ctx.pop(False)
        return

    # Since it was not a start tag, it should be an end tag
    m = re.match(r"<\s*/\s*([-a-zA-Z0-9]+)\s*>", token)
    assert m  # If fails, then mismatch between regexp here and tokenization
    name = m.group(1)
    name = name.lower()
    if name == "nowiki":
        # Handle </nowiki> end tag
        if ctx.nowiki:
            ctx.nowiki = False
            # Cause certain special behaviors to be suppressed,
            # particularly link trail processing.  This will be
            # automatically reset when the next child is inserted in
            # ctx.push().
            ctx.suppress_special = True
        else:
            ctx.error("unexpected </nowiki>")
            text_fn(ctx, token)
        return
    if name == "pre":
        # Handle </pre> end tag
        node = ctx.stack[-1]
        if node.kind != NodeKind.PRE:
            ctx.error("unexpected </pre>")
            text_fn(ctx, token)
            return
        ctx.pop(False)
        return

    if name not in ALLOWED_HTML_TAGS:
        ctx.error("html tag </{}> not allowed in WikiText"
                  "".format(name))
        text_fn(ctx, token)
        return

    # Push a HTML node for the end tag
    node = ctx.push(NodeKind.HTML)
    node.args = name
    node.attrs["_close"] = True
    ctx.pop(False)


def magicword_fn(ctx, token):
    node = ctx.push(NodeKind.MAGIC_WORD)
    node.args = token
    ctx.pop(False)


# Regular expression for matching a token in WikiMedia text
token_re = re.compile(r"(?m)^(={2,6})\s*(([^=]|=[^=])+?)\s*(={2,6})\s*$|"
                      r"'''|"
                      r"''|"
                      r" |"   # Space at beginning of line means preformatted
                      r"\n|"
                      r"\t|"
                      r"\[\[|"
                      r"\]\]|"
                      r"\[|"
                      r"\]|"
                      r"\{\{+|"
                      r"\}\}+|"
                      r"\|\}+|"
                      r"\{\||"
                      r"\|\+|"
                      r"\|-|"
                      r"^!|"
                      r"!!|"
                      r"\|\||"
                      r"\||"
                      r"^----+|"
                      r"^[-*:;#]+\s*|"
                      r":|"   # sometimes special when not beginning of line
                      r"<!\s*--((?s).)*?--\s*>|"
                      r"""<\s*[-a-zA-Z0-9]+\s*(\b[-a-z0-9]+(=("[^"]*"|"""
                      r"""'[^']*'|[^ \t\n"'`=<>]*))?\s*)*(/\s*)?>|"""
                      r"<\s*/\s*[-a-zA-Z0-9]+\s*>|"
                      r"https?://[a-zA-Z0-9.]+|"
                      r":|" +
                      r"(" +
                      r"|".join(r"\b{}\b".format(x) for x in MAGIC_WORDS) +
                      r")")

# Dictionary mapping fixed form tokens to handler functions.
tokenops = {
    "'''": bold_fn,
    "''": italic_fn,
    "[[": ilink_start_fn,
    "]]": ilink_end_fn,
    "[": elink_start_fn,
    "]": elink_end_fn,
    "{{{": templarg_start_fn,
    "}}}": templarg_end_fn,
    "{{": templ_start_fn,
    "}}": templ_end_fn,
    "{|": table_start_fn,
    "|}": table_end_fn,
    "|+": table_caption_fn,
    "!": table_hdr_cell_fn,
    "!!": table_hdr_cell_fn,
    "|-": table_row_fn,
    "||": double_vbar_fn,
    "|": vbar_fn,
    " ": whitespace_fn,
    "\n": whitespace_fn,
    "\t": whitespace_fn,
}
for x in MAGIC_WORDS:
    tokenops[x] = magicword_fn


def token_iter(text):
    """Tokenizes MediaWiki page content.  This yields (is_token, text) for
    each token.  ``is_token`` is False for text and True for other tokens."""
    assert isinstance(text, str)
    pos = 0
    for m in re.finditer(token_re, text):
        start = m.start()
        if pos != start:
            yield False, text[pos:start]
        pos = m.end()
        token = m.group(0)
        if token.startswith("=="):
            yield True, "<" + m.group(1)
            for x in token_iter(m.group(2)):
                yield x
            yield True, ">" + m.group(4)
        elif token.startswith("{{"):
            toklen = len(token)
            if toklen in (2, 3):
                yield True, token
            elif toklen == 4:
                yield True, "{{"
                yield True, "{{"
            elif toklen == 5:
                yield True, "{{"
                yield True, "{{{"
            elif toklen == 6:
                yield True, "{{{"
                yield True, "{{{"
            else:
                print("Unsupported brace sequence {}".format(token))
                yield False, token
        elif token.startswith("}}"):
            toklen = len(token)
            if toklen in (2, 3):
                yield True, token
            elif toklen == 4:
                yield True, "}}"
                yield True, "}}"
            elif toklen == 5:
                yield True, "}}}"
                yield True, "}}"
            elif toklen == 6:
                yield True, "}}}"
                yield True, "}}}"
            else:
                print("Unsupported brace sequence {}".format(token))
                yield False, token
        elif token.startswith("|}}"):
            yield True, "|"
            token = token[1:]
            toklen = len(token)
            if toklen in (2, 3):
                yield True, token
            elif toklen == 4:
                yield True, "}}"
                yield True, "}}"
            elif toklen == 5:
                yield True, "}}}"
                yield True, "}}"
            elif toklen == 6:
                yield True, "}}}"
                yield True, "}}}"
            else:
                print("Unsupported brace sequence {}".format(token))
                yield False, token
        else:
            yield True, token
    if pos != len(text):
        yield False, text[pos:]


def parse_with_ctx(pagetitle, text):
    """Parses a Wikitext document into a tree.  This returns a WikiNode object
    that is the root of the parse tree and the parse context."""
    assert isinstance(pagetitle, str)
    assert isinstance(text, str)
    # Create parse context.  This also pushes a ROOT node on the stack.
    ctx = ParseCtx(pagetitle)
    # Process all tokens from the input.
    for is_token, token in token_iter(text):
        assert isinstance(token, str)
        node = ctx.stack[-1]
        if (not is_token or
            (ctx.nowiki and
             not re.match(r"(?i)<\s*/\s*nowiki\s*>", token)) or
            (node.kind == NodeKind.PRE and
             not re.match(r"(?i)<\s*/\s*pre\s*>", token))):
            if is_token:
                # Remove the artificially added prefix from subtitle tokens
                if token.startswith("<=="):
                    token = token[1:]
                elif token.startswith(">=="):
                    token = token[1:]
            text_fn(ctx, token)
        else:
            if token in tokenops:
                tokenops[token](ctx, token)
            elif token.startswith("<=="):  # Note: < added by tokenizer
                subtitle_start_fn(ctx, token)
            elif token.startswith(">=="):  # Note: > added by tokenizer
                subtitle_end_fn(ctx, token)
            elif token.startswith("----"):
                hline_fn(ctx, token)
            elif token.startswith("<") and len(token):
                tag_fn(ctx, token)
            elif re.match(r"[-*:;#]+", token):
                list_fn(ctx, token)
            elif re.match(r"https?://.*", token):
                url_fn(ctx, token)
            else:
                text_fn(ctx, token)
        ctx.linenum += len(list(re.finditer("\n", token)))
        ctx.beginning_of_line = token.endswith("\n")
    while True:
        node = ctx.stack[-1]
        if node.kind == NodeKind.ROOT:
            break
        ctx.pop(True)
    assert len(ctx.stack) == 1
    return ctx.stack[0], ctx


def parse(pagetitle, text):
    """Parse a wikitext document into a tree.  This returns a WikiNode
    object that is the root of the parse tree and the parse context.
    This does not expand HTML entities; that should be done after processing
    templates."""
    assert isinstance(pagetitle, str)
    assert isinstance(text, str)
    tree, ctx = parse_with_ctx(pagetitle, text)
    return tree


def print_tree(tree, indent):
    """Prints the parse tree for debugging purposes.  This does not expand
    HTML entities; that should be done after processing templates."""
    assert isinstance(tree, (WikiNode, str))
    assert isinstance(indent, int)
    if isinstance(tree, str):
        print("{}{}".format(" " * indent, repr(tree)))
        return
    print("{}{} {}".format(" " * indent, tree.kind.name, tree.args))
    for child in tree.children:
        print_tree(child, indent + 2)


# Very simple test:
# data = open("pages/Words/ho/horse.txt", "r").read()
# tree = parse("horse", data)
# print_tree(tree, 0)