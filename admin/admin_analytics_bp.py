from flask import Blueprint, render_template
from utils.analytics import get_demo_views

admin_analytics_bp = Blueprint('admin_analytics', __name__, template_folder='templates')

class DemoViewCount:
    def __init__(self, demo_id, count):
        self.id = demo_id
        self.views = count

    def __repr__(self):
        return f"DemoViewCount({self.id}, {self.views})"

    def __str__(self):
        return f"Demo ID: {self.id}, Count: {self.views}"

def count_per_demo(data):
    demo_count = {}
    for view in data:
        demo_id = view.get("demo_id")
        if demo_id in demo_count:
            demo_count[demo_id] += 1
        else:
            demo_count[demo_id] = 1
    
    demo_count = [DemoViewCount(demo_id, count) for demo_id, count in demo_count.items()]
    return demo_count

@admin_analytics_bp.route('/admin/analytics')
def admin_analytics():
    data = get_demo_views()
    data = count_per_demo(data)
    
    
    return render_template('admin/analytics.html', data=data)