"""
This file contains code for a test of new kind of control panel stuff, that would make creating the control panels a lot easier.
"""

@app.route("/admin/control_panel", methods=["GET"])
def control_panel():
    # Example items data
    items = mongo.demonstrations.find()

    # Configuration for the table
    config = {
        "name": "Demos",
        "columns": [
            {"label": "Otsikko", "key": "title"},
            # Add other columns as needed
        ],
        "actions": [
            {
                "label": "Muokkaa",
                "icon": "edit",
                "url": "admin_demo.edit_demo",
                "values": {"demo_id": None},
            },
            {
                "label": "Poista",
                "icon": "trash",
                "url": "admin_demo.delete_demo",
                "values": {"demo_id": None},
            },  # Place holder, will be replaced later                    },               },
        ],
    }

    search_query = request.args.get("search", "")

    return render_template(
        "admin/mac_test.html", items=items, config=config, search_query=search_query
    )
