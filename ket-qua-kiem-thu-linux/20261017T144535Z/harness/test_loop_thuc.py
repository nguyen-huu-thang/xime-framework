import asyncio
import os
import pytest

@pytest.mark.asyncio
async def test_loop_thuc():
    loop = asyncio.get_running_loop()
    name = type(loop).__module__ + '.' + type(loop).__qualname__
    print('LOOP_THUC=' + name, flush=True)
    assert name.startswith('uvloop.') == (os.environ['LOOP_MONG_DOI'] == 'uvloop')
