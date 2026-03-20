"""Report generator for creating test reports."""
from datetime import datetime
from typing import Any

from app.models.task import Task
from app.models.task_step import TaskStep
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """Generates test reports from task execution data."""

    def generate_report_data(self, task: Task, steps: list[TaskStep]) -> dict[str, Any]:
        """Generate report data structure.

        Args:
            task: Task model
            steps: List of task steps

        Returns:
            Report data dict
        """
        # Calculate statistics
        total_steps = len(steps)
        passed_steps = sum(1 for s in steps if s.status == "completed")
        failed_steps = sum(1 for s in steps if s.status == "failed")
        skipped_steps = sum(1 for s in steps if s.status == "skipped")

        # Calculate durations
        total_duration = sum(s.duration_ms or 0 for s in steps)
        avg_step_duration = total_duration / total_steps if total_steps > 0 else 0

        # Find failed steps
        failed_step_details = []
        for step in steps:
            if step.status == "failed":
                failed_step_details.append(
                    {
                        "step_index": step.step_index,
                        "action": step.action,
                        "target": step.target,
                        "error": step.error_detail,
                        "retries": step.retry_count,
                        "fix_applied": step.fix_applied,
                    }
                )

        # Build report
        report = {
            "report_id": f"report_{task.task_id}",
            "task_id": task.task_id,
            "summary": {
                "status": task.status,
                "total_steps": total_steps,
                "passed_steps": passed_steps,
                "failed_steps": failed_steps,
                "skipped_steps": skipped_steps,
                "pass_rate": (passed_steps / total_steps * 100) if total_steps > 0 else 0,
                "total_duration_ms": total_duration,
                "avg_step_duration_ms": avg_step_duration,
                "start_time": task.created_at.isoformat() if task.created_at else None,
                "end_time": task.updated_at.isoformat() if task.updated_at else None,
            },
            "instruction": task.instruction,
            "device": {
                "device_id": task.device_id,
            },
            "steps": [
                {
                    "step_index": s.step_index,
                    "action": s.action,
                    "target": s.target,
                    "value": s.value,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "retry_count": s.retry_count,
                    "fix_applied": s.fix_applied,
                    "screenshot_before": s.screenshot_before,
                    "screenshot_after": s.screenshot_after,
                    "error_detail": s.error_detail,
                }
                for s in steps
            ],
            "failures": failed_step_details,
            "errors": [
                {
                    "type": task.error_type,
                    "message": task.error_message,
                }
            ] if task.error_type else [],
            "generated_at": datetime.utcnow().isoformat(),
        }

        logger.debug(f"Generated report for task {task.task_id}")
        return report

    def generate_html(self, task: Task, steps: list[TaskStep]) -> str:
        """Generate HTML report.

        Args:
            task: Task model
            steps: List of task steps

        Returns:
            HTML content string
        """
        report_data = self.generate_report_data(task, steps)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Report - {task.task_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f7fa;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: #667eea;
        }}
        .stat-label {{
            color: #666;
            font-size: 14px;
        }}
        .passed {{ color: #67c23a; }}
        .failed {{ color: #f56c6c; }}
        .skipped {{ color: #909399; }}
        .card {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            overflow: hidden;
        }}
        .card-header {{
            background: #f5f7fa;
            padding: 15px 20px;
            font-weight: bold;
            border-bottom: 1px solid #eee;
        }}
        .card-body {{
            padding: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background: #f5f7fa;
            font-weight: 600;
        }}
        .status-badge {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }}
        .status-completed {{ background: #e7f7e7; color: #67c23a; }}
        .status-failed {{ background: #fef0f0; color: #f56c6c; }}
        .status-pending {{ background: #f5f5f5; color: #909399; }}
        .status-running {{ background: #ecf5ff; color: #409eff; }}
        .instruction {{
            background: #f5f7fa;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            margin-bottom: 20px;
        }}
        .error-detail {{
            background: #fef0f0;
            border-left: 4px solid #f56c6c;
            padding: 15px;
            margin: 10px 0;
        }}
        .footer {{
            text-align: center;
            color: #999;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #eee;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Test Execution Report</h1>
        <p>Task ID: {task.task_id}</p>
    </div>

    <div class="summary">
        <div class="stat-card">
            <div class="stat-value">{report_data['summary']['total_steps']}</div>
            <div class="stat-label">Total Steps</div>
        </div>
        <div class="stat-card">
            <div class="stat-value passed">{report_data['summary']['passed_steps']}</div>
            <div class="stat-label">Passed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value failed">{report_data['summary']['failed_steps']}</div>
            <div class="stat-label">Failed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{report_data['summary']['pass_rate']:.1f}%</div>
            <div class="stat-label">Pass Rate</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{report_data['summary']['total_duration_ms'] / 1000:.1f}s</div>
            <div class="stat-label">Duration</div>
        </div>
    </div>

    <div class="card">
        <div class="card-header">Test Instruction</div>
        <div class="card-body">
            <div class="instruction">{task.instruction}</div>
        </div>
    </div>

    <div class="card">
        <div class="card-header">Execution Steps</div>
        <div class="card-body">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Action</th>
                        <th>Target</th>
                        <th>Value</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Retries</th>
                    </tr>
                </thead>
                <tbody>
"""

        for step in report_data["steps"]:
            status_class = f"status-{step['status']}"
            duration = f"{step['duration_ms'] / 1000:.1f}s" if step['duration_ms'] else "-"

            html += f"""
                    <tr>
                        <td>{step['step_index']}</td>
                        <td>{step['action']}</td>
                        <td>{step['target'] or '-'}</td>
                        <td>{step['value'] or '-'}</td>
                        <td><span class="status-badge {status_class}">{step['status']}</span></td>
                        <td>{duration}</td>
                        <td>{step['retry_count']}</td>
                    </tr>
"""

            if step.get("error_detail"):
                html += f"""
                    <tr>
                        <td colspan="7">
                            <div class="error-detail">
                                <strong>Error:</strong> {step['error_detail']}
                                {"<br><strong>Fix Applied:</strong> " + step['fix_applied'] if step.get('fix_applied') else ""}
                            </div>
                        </td>
                    </tr>
"""

        html += f"""
                </tbody>
            </table>
        </div>
    </div>
"""

        if report_data.get("errors"):
            html += """
    <div class="card">
        <div class="card-header">Task Errors</div>
        <div class="card-body">
"""
            for error in report_data["errors"]:
                html += f"""
            <div class="error-detail">
                <strong>Type:</strong> {error.get('type', 'Unknown')}<br>
                <strong>Message:</strong> {error.get('message', 'No message')}
            </div>
"""
            html += """
        </div>
    </div>
"""

        html += f"""
    <div class="footer">
        <p>Generated at {report_data['generated_at']}</p>
        <p>APP Automated Testing Platform</p>
    </div>
</body>
</html>
"""

        return html
