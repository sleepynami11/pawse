"""
Scheduled Task Utility for Cloudflare Cron Triggers

This module provides handlers for automated weekly report generation
triggered by Cloudflare Workers Cron Triggers.

Environment Variables Required:
    - D1_DATABASE_ID: The D1 database ID
    - CLOUDFLARE_API_TOKEN: Cloudflare API token with D1 permissions
    - CLOUDFLARE_ACCOUNT_ID: Cloudflare account ID
    - R2_ACCESS_KEY_ID: R2 access key ID
    - R2_SECRET_ACCESS_KEY: R2 secret access key
    - R2_ENDPOINT_URL: R2 endpoint URL

Cron Schedule Configuration (wrangler.toml):
    [triggers]
    crons = ["0 8 * * 0"]  # Every Sunday at 8:00 AM UTC

Usage Example:
    # Manual trigger (for testing)
    import asyncio
    from utils.scheduled_tasks import run_weekly_reports

    async def main():
        result = await run_weekly_reports()
        print(result)

    asyncio.run(main())

    # Cloudflare Workers Cron Trigger
    from utils.scheduled_tasks import handle_cron_trigger

    async def scheduled(event):
        return await handle_cron_trigger()
"""

import asyncio
import logging
from datetime import datetime
from pocketflow import AsyncFlow
from context_manager import SystemContext
from nodes import WeeklyReportNode
from utils.d1_client import execute_query

logger = logging.getLogger(__name__)


async def run_weekly_reports() -> dict:
    """
    Execute weekly report generation for all active cats.

    This function queries the database for all active cats and generates
    a weekly health report for each one using the WeeklyReportNode flow.

    Returns:
        dict: Summary containing:
            - total (int): Total number of cats processed
            - success (int): Number of successful report generations
            - failures (int): Number of failed report generations
            - errors (list): List of error details for failed reports

    Example:
        result = await run_weekly_reports()
        print(f"Generated {result['success']} reports out of {result['total']} cats")
    """
    logger.info("Starting weekly report generation task")
    start_time = datetime.now()

    # Query D1 for all active cats
    try:
        result = await execute_query(
            "SELECT id, name FROM cats WHERE 1=1"  # Assuming all cats are active by default
        )

        if not result.get("success") or not result.get("result", {}).get("results"):
            logger.warning("No active cats found in database")
            return {
                'total': 0,
                'success': 0,
                'failures': 0,
                'errors': [],
                'execution_time': 0
            }

        cats = result["result"]["results"]
        logger.info(f"Found {len(cats)} active cats for weekly report generation")

    except Exception as e:
        logger.error(f"Failed to query active cats: {str(e)}")
        return {
            'total': 0,
            'success': 0,
            'failures': 0,
            'errors': [{'error': str(e), 'stage': 'database_query'}],
            'execution_time': 0
        }

    # Process each cat
    total_cats = len(cats)
    success_count = 0
    failure_count = 0
    errors = []

    for cat in cats:
        cat_id = str(cat.get('id'))
        cat_name = cat.get('name', 'Unknown')

        try:
            logger.info(f"Generating weekly report for cat {cat_id} ({cat_name})")

            # Create WeeklyReportNode flow
            weekly_report_node = WeeklyReportNode()
            flow = AsyncFlow(start=weekly_report_node)

            # Initialize shared store
            shared = {
                'cat_id': cat_id,
                'report_type': 'weekly'
            }

            # Execute flow
            await flow.run_async(shared)

            # Check if report was generated
            if 'weekly_report' in shared:
                success_count += 1
                logger.info(f"Successfully generated weekly report for cat {cat_id}")
            else:
                failure_count += 1
                error_msg = f"Report generation completed but no report found in shared store"
                logger.error(f"Cat {cat_id}: {error_msg}")
                errors.append({
                    'cat_id': cat_id,
                    'cat_name': cat_name,
                    'error': error_msg,
                    'stage': 'report_validation'
                })

        except Exception as e:
            failure_count += 1
            error_msg = str(e)
            logger.error(f"Failed to generate report for cat {cat_id}: {error_msg}")
            errors.append({
                'cat_id': cat_id,
                'cat_name': cat_name,
                'error': error_msg,
                'stage': 'report_generation'
            })

    # Calculate execution time
    end_time = datetime.now()
    execution_time = (end_time - start_time).total_seconds()

    # Log summary
    logger.info(f"Weekly report generation completed: {success_count}/{total_cats} succeeded, {failure_count} failed (took {execution_time:.2f}s)")

    return {
        'total': total_cats,
        'success': success_count,
        'failures': failure_count,
        'errors': errors,
        'execution_time': execution_time,
        'timestamp': start_time.isoformat()
    }


def handle_cron_trigger() -> dict:
    """
    Cloudflare Workers Cron Trigger handler.

    This function is called by Cloudflare Workers when the cron schedule is triggered.
    It wraps the async run_weekly_reports() function for compatibility with
    Cloudflare Workers event model.

    Returns:
        dict: Same as run_weekly_reports() - summary of report generation results

    Example (in worker.py):
        from utils.scheduled_tasks import handle_cron_trigger

        async def scheduled(event, env, ctx):
            result = handle_cron_trigger()
            return result
    """
    logger.info("Cron trigger received - starting weekly report generation")

    # Run async function in event loop
    result = asyncio.run(run_weekly_reports())

    logger.info(f"Cron trigger completed - {result['success']}/{result['total']} reports generated")

    return result


if __name__ == "__main__":
    # Manual testing
    async def test():
        """Test weekly report generation manually"""
        print("=== Testing Weekly Report Generation ===")
        result = await run_weekly_reports()
        print(f"\nResults:")
        print(f"  Total cats: {result['total']}")
        print(f"  Successful reports: {result['success']}")
        print(f"  Failed reports: {result['failures']}")
        print(f"  Execution time: {result['execution_time']:.2f}s")

        if result['errors']:
            print(f"\nErrors ({len(result['errors'])}):")
            for error in result['errors']:
                print(f"  - Cat {error['cat_id']} ({error['cat_name']}): {error['error']}")

    asyncio.run(test())
