#!/usr/bin/env python3
"""Test for AutoGLM agent executor - 打开山海app发帖子.

Usage:
    source venv/bin/activate
    python tests/test_autoglm_agent.py

Requires:
    - ADB device connected
    - Valid MINIMAX_API_KEY for AutoGLM
    - Valid QWEN_API_KEY for decision making
"""

import asyncio
import sys
import os

# Load .env first
from dotenv import load_dotenv

# Try multiple paths for .env
_env_paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
]
for _env_path in _env_paths:
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
        break

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.agent.executor import AgentExecutor, ExecutionStep, ExecutionHistory
from app.core.agent.step_executor import StepExecutor
from app.core.agent.prompt import AgentPromptTemplate
from app.llm.providers.autoglm import AutoGLMProvider
from app.llm.factory import LLMFactory
from app.core.script.template import MaestroTemplate
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


def load_config():
    """Load LLM config from yaml."""
    import yaml

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..",
        "config",
        "backend",
        "llm.yaml",
    )
    with open(config_path) as f:
        config = yaml.safe_load(f)

    def expand_env(var):
        if isinstance(var, str) and var.startswith("${") and var.endswith("}"):
            env_name = var[2:-1]
            return os.environ.get(env_name, "")
        return var

    providers = config.get("providers", {})
    for name, p in providers.items():
        for k, v in p.items():
            if isinstance(v, str):
                p[k] = expand_env(v)

    return config


async def test_step_executor():
    """Test step executor basic operations."""
    print("\n" + "=" * 60)
    print("Test 1: StepExecutor Basic Operations")
    print("=" * 60)

    executor = StepExecutor("5PAMPJYTTSHEBASO")

    # Test screenshot
    print("\n  Taking screenshot...")
    screenshot = await executor.screenshot()
    print(f"  Screenshot size: {len(screenshot)} bytes")
    assert len(screenshot) > 0, "Screenshot should not be empty"

    # Get screen resolution
    print("\n  Getting screen resolution...")
    width, height = await executor.adb.get_screen_resolution()
    print(f"  Screen: {width}x{height}")

    # Get current app
    print("\n  Getting current app...")
    current_app = await executor.adb.get_top_activity()
    print(f"  Current app: {current_app[0]}")
    print(f"  Activity: {current_app[1]}")

    # Test wait
    print("\n  Testing wait action...")
    result = await executor.execute_step({"action": "waitForAnimationToEnd"})
    print(f"  Result: {result}")
    assert result.get("success"), "Wait should succeed"

    print("\n✓ StepExecutor tests PASSED")


async def test_prompt_template():
    """Test prompt template formatting with coordinates."""
    print("\n" + "=" * 60)
    print("Test 2: Prompt Template with Coordinates")
    print("=" * 60)

    elements = [
        {
            "type": "EditText",
            "text": "搜索",
            "bounds": {"x": 100, "y": 50, "width": 880, "height": 80},
            "resource_id": "search_id",
        },
        {
            "type": "ImageView",
            "text": "山海app图标",
            "bounds": {"x": 200, "y": 300, "width": 150, "height": 150},
            "resource_id": "",
        },
        {
            "type": "Button",
            "text": "发布",
            "bounds": {"x": 500, "y": 1800, "width": 200, "height": 80},
            "resource_id": "publish_btn",
        },
    ]

    formatted = AgentPromptTemplate.format_elements(elements)
    print("\n  Formatted elements:")
    for line in formatted.split("\n"):
        print(f"    {line}")

    # Verify relative coordinates (0-999 system) - Open-AutoGLM format
    # Element 1: center_x = 100 + 880/2 = 540, center_y = 50 + 80/2 = 90
    #           rel_x = int(540/1080 * 999) = 499, rel_y = int(90/1920 * 999) = 46
    assert "→ element=[499,46]" in formatted

    # Element 2: center_x = 200 + 150/2 = 275, center_y = 300 + 150/2 = 375
    #           rel_x = int(275/1080 * 999) = 254, rel_y = int(375/1920 * 999) = 195
    assert "→ element=[254,195]" in formatted

    # Element 3: center_x = 500 + 200/2 = 600, center_y = 1800 + 80/2 = 1840
    #           rel_x = int(600/1080 * 999) = 555, rel_y = int(1840/1920 * 999) = 957
    assert "→ element=[555,957]" in formatted

    history = [
        {"action": "tapOn", "target": "搜索框", "success": True, "x": 540, "y": 90},
    ]
    hist_formatted = AgentPromptTemplate.format_history(history)
    print(f"\n  Formatted history: {hist_formatted}")

    # Test full prompt build
    system_prompt, user_prompt = AgentPromptTemplate.build_decision_prompt(
        goal="打开山海app并发布帖子",
        current_app="com.android.launcher",
        page_type="home",
        page_description="手机桌面",
        elements=elements,
        history=history,
    )

    assert "→ element=[499,46]" in user_prompt
    assert "山海app" in user_prompt
    print("\n✓ Prompt template tests PASSED")


async def test_executor_dataclass():
    """Test executor dataclasses with coordinates."""
    print("\n" + "=" * 60)
    print("Test 3: Executor Dataclasses")
    print("=" * 60)

    # Test ExecutionStep with coordinates
    step = ExecutionStep(
        action="tapOn",
        target="搜索框",
        x=540,
        y=90,
    )
    print(f"\n  ExecutionStep: action={step.action}, x={step.x}, y={step.y}")
    assert step.x == 540
    assert step.y == 90

    # Test ExecutionHistory
    history = ExecutionHistory()
    history.add(step)
    history_list = history.to_list()
    print(f"  History to_list: {history_list[0]}")
    assert history_list[0]["x"] == 540
    assert history_list[0]["y"] == 90

    # Test MaestroTemplate with coordinates
    steps = [
        {"action": "tapOn", "x": 540, "y": 90, "target": "搜索框"},
        {"action": "inputText", "value": "山海"},
        {"action": "tapOn", "x": 275, "y": 375, "target": "山海app图标"},
        {"action": "launchApp", "target": "com.shanhai.app"},
    ]
    template = MaestroTemplate()
    yaml_output = template.render(steps, "com.android.launcher", "打开山海app")

    assert "point: 540,90" in yaml_output
    assert "point: 275,375" in yaml_output
    print("\n  Generated YAML includes point: coordinates")

    print("\n✓ Executor dataclasses tests PASSED")


async def test_autoglm_vision(config):
    """Test AutoGLM vision analysis."""
    print("\n" + "=" * 60)
    print("Test 4: AutoGLM Vision Analysis")
    print("=" * 60)

    autoglm_config = config["providers"]["autoglm"]
    print(f"\n  API Base: {autoglm_config.get('api_base')}")
    print(f"  Model: {autoglm_config.get('model')}")

    autoglm = AutoGLMProvider(autoglm_config)

    executor = StepExecutor("5PAMPJYTTSHEBASO")
    screenshot = await executor.screenshot()
    print(f"\n  Screenshot: {len(screenshot)} bytes")

    print("\n  Analyzing screenshot...")
    result = await autoglm.analyze_screenshot(
        screenshot,
        context="用户目标: 打开山海app并发布帖子",
    )

    print(f"  Page type: {result.page_type}")
    print(f"  Elements found: {len(result.elements)}")
    print(f"  Description: {result.overall_description[:200] if result.overall_description else 'N/A'}...")

    if result.elements:
        print("\n  First 5 elements:")
        for elem in result.elements[:5]:
            print(f"    - [{elem.element_type}] text={elem.text} bounds={elem.bounds}")

    await autoglm.close()
    print("\n✓ AutoGLM vision tests PASSED")


async def test_qwen_decision(config):
    """Test Qwen for AI decision making."""
    print("\n" + "=" * 60)
    print("Test 5: Qwen AI Decision Making")
    print("=" * 60)

    qwen_config = config["providers"]["qwen"]
    print(f"\n  API Base: {qwen_config.get('api_base')}")
    print(f"  Model: {qwen_config.get('models', {}).get('primary')}")

    # Create Qwen provider
    qwen = LLMFactory.create("qwen", qwen_config)

    elements = [
        {"type": "EditText", "text": "搜索", "bounds": {"x": 100, "y": 50, "width": 880, "height": 80}, "resource_id": "search"},
        {"type": "ImageView", "text": "山海app图标", "bounds": {"x": 200, "y": 300, "width": 150, "height": 150}, "resource_id": ""},
    ]

    system_prompt, user_prompt = AgentPromptTemplate.build_decision_prompt(
        goal="打开山海app",
        current_app="com.android.launcher",
        page_type="home",
        page_description="手机桌面",
        elements=elements,
        history=[],
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    print("\n  Sending decision request to Qwen...")
    response = await qwen.chat(messages)
    print(f"\n  Qwen response (first 500 chars):")
    print(f"  {response.content[:500]}...")

    # Parse response using parse_answer (Open-AutoGLM format)
    content = response.content.strip()
    parsed = AgentPromptTemplate.parse_answer(content)

    print(f"\n  Parsed decision (Open-AutoGLM format):")
    print(f"    _metadata: {parsed.get('_metadata')}")
    print(f"    action: {parsed.get('action')}")
    print(f"    element: {parsed.get('element')}")

    # Verify it's a proper Open-AutoGLM action
    assert parsed.get("_metadata") == "do", "Should be a 'do' action"
    assert parsed.get("action") == "Tap", "Action should be 'Tap'"
    assert parsed.get("element") is not None, "Should have element coordinates"

    print("\n✓ Qwen decision tests PASSED")


async def test_full_agent_flow(config):
    """Test full agent executor flow (limited iterations)."""
    print("\n" + "=" * 60)
    print("Test 6: Full Agent Executor Flow")
    print("=" * 60)
    print("\n  Instruction: 打开山海app发一个帖子")
    print("  (Limited to 3 iterations for testing)")

    llm_config = config["providers"]["qwen"]
    autoglm_config = config["providers"]["autoglm"]

    executor = AgentExecutor(
        device_serial="5PAMPJYTTSHEBASO",
        llm_config=llm_config,
        autoglm_config=autoglm_config,
    )

    # Limit iterations for testing
    original_max = executor.MAX_ITERATIONS
    executor.MAX_ITERATIONS = 3

    try:
        result = await executor.execute(
            instruction="打开山海app发一个帖子",
            task_id="test-001",
        )

        print(f"\n  Execution completed:")
        print(f"    Success: {result.get('success')}")
        print(f"    Iterations: {result.get('iterations')}")
        print(f"    Goal: {result.get('goal')}")
        print(f"    Steps: {len(result.get('steps', []))}")

        print(f"\n  Generated Script:")
        print("  " + "-" * 50)
        print(result.get("generated_script", "No script"))
        print("  " + "-" * 50)

        print(f"\n  Step details:")
        for i, step in enumerate(result.get("steps", []), 1):
            x = step.get("x")
            y = step.get("y")
            coord_str = f" ({x}, {y})" if x and y else ""
            print(f"    {i}. {step.get('action')}{coord_str}: {step.get('target') or step.get('value')}")

    except Exception as e:
        print(f"\n  Execution error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        executor.MAX_ITERATIONS = original_max
        await executor.close()

    print("\n✓ Full agent flow test completed")


async def main():
    """Run all tests."""
    print("=" * 60)
    print("AutoGLM Agent Test Suite")
    print("打开山海app发帖子")
    print("=" * 60)

    setup_logging()

    # Load config
    try:
        config = load_config()
        print("\nConfig loaded successfully")
    except Exception as e:
        print(f"\nFailed to load config: {e}")
        print("Using default configs...")
        config = {
            "providers": {
                "autoglm": {
                    "api_key": os.getenv("AUTOGLM_API_KEY", ""),
                    "api_base": "https://api.minimax.chat/v",
                    "model": "auto-glm-vision",
                },
                "qwen": {
                    "api_key": os.getenv("QWEN_API_KEY", ""),
                    "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen-plus",
                },
            }
        }

    # Run tests
    await test_step_executor()
    await test_prompt_template()
    await test_executor_dataclass()

    # These require valid API keys
    await test_autoglm_vision(config)
    await test_qwen_decision(config)
    await test_full_agent_flow(config)

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
