"""Browse a real OPC UA server started inside the test: the cases the simulated panel does not have."""
import asyncio

from asyncua import Server, ua

from opcua_tagmap.browse import browse

ENDPOINT = "opc.tcp://127.0.0.1:48461/plant/"


async def _serve(ready: asyncio.Event, stop: asyncio.Event) -> None:
    server = Server()
    await server.init()
    server.set_endpoint(ENDPOINT)
    idx = await server.register_namespace("urn:test:plant")
    plant = await server.nodes.objects.add_object(idx, "Plant")
    for loop in ("TIC101", "TI102"):                      # two loops, each with a variable called PV
        obj = await plant.add_object(idx, loop)
        await obj.add_variable(idx, "PV", 1.0)
    # A structured variable with member variables and one property, as PLCs expose a STRUCT
    recipe = await plant.add_variable(idx, "Recipe", 0)
    await recipe.add_variable(idx, "Setpoint", 50.0)
    await recipe.add_variable(idx, "Duration", 10)
    await recipe.add_property(idx, "EngineeringUnits", "s")
    async with server:
        ready.set()
        await stop.wait()


async def _browse(**kw):
    ready, stop = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(_serve(ready, stop))
    await asyncio.wait_for(ready.wait(), 20)
    try:
        return await browse(ENDPOINT, **kw)
    finally:
        stop.set()
        await task


def test_members_of_a_structured_variable_are_found():
    paths = [t.browse_path for t in asyncio.run(_browse()).tags]
    assert "Objects/Plant/Recipe" in paths
    assert "Objects/Plant/Recipe/Setpoint" in paths and "Objects/Plant/Recipe/Duration" in paths


def test_properties_of_a_variable_are_not_tags():
    paths = [t.browse_path for t in asyncio.run(_browse()).tags]
    assert not any(p.endswith("EngineeringUnits") for p in paths)


def test_same_name_under_two_parents_gives_two_tags():
    tags = [t for t in asyncio.run(_browse()).tags if t.display_name == "PV"]
    assert [t.browse_path for t in tags] == ["Objects/Plant/TI102/PV", "Objects/Plant/TIC101/PV"]


def test_depth_limit_still_applies():
    paths = [t.browse_path for t in asyncio.run(_browse(max_depth=0)).tags]
    assert paths == []                                    # depth 0 lists nothing below Objects/Plant
