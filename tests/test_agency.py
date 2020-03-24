import httpagentparser

from recapturedocs import agency


def test_httpagent_parser_odd():
    UA = 'Mozilla/4.0 (compatible; Powermarks/3.5; Windows 95/98/2000/NT)'
    agent = agency.AgentHelper(httpagentparser.detect(UA))
    assert not agent.IE_lt('9.0')


def test_httpagent_parser_ie():
    UA = (
        'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.1; '
        'Trident/4.0; GTB6.5; QQDownload 534; Mozilla/4.0 '
        '(compatible; MSIE 6.0; Windows NT 5.1; SV1) ; '
        'SLCC2; .NET CLR 2.0.50727; Media Center PC 6.0; '
        '.NET CLR 3.5.30729; .NET CLR 3.0.30729'
    )
    agent = agency.AgentHelper(httpagentparser.detect(UA))
    assert agent.IE_lt('9.0')


def test_httpagent_parser_blank():
    agent = agency.AgentHelper(httpagentparser.detect(''))
    assert not agent.IE_lt('9.0')
