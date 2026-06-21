from storygraph.demo import PROJECT_ID, SCENE_ID, build_fantasy_demo_graph


def test_fantasy_demo_defaults_to_english_contract_fixture():
    graph = build_fantasy_demo_graph()

    project = graph.get_node(PROJECT_ID)
    scene = graph.get_node(SCENE_ID)

    assert project.properties["title"] == "Fantasy Demo"
    assert scene.properties["title"] == "The Tower Search"


def test_fantasy_demo_supports_chinese_localized_fixture():
    graph = build_fantasy_demo_graph(locale="zh-CN")

    project = graph.get_node(PROJECT_ID)
    scene = graph.get_node(SCENE_ID)

    assert project.properties["title"] == "奇幻演示"
    assert scene.properties["title"] == "钟塔搜寻"
    assert scene.properties["goal"] == "寻找遗失的密封信"
