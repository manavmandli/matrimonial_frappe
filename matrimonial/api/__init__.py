import frappe
from bs4 import BeautifulSoup

def get_endpoint_details(api_name):
    """
    Retrieve endpoint configuration from API Gateway Doctype based on API Name.
    """
    try:
        endpoint_doc = frappe.get_doc("API Gateway", {"api_name": api_name})
        endpoint_details = {
            "methods": {endpoint_doc.method_type},
            "function": endpoint_doc.api_name,
            "allow_guest": endpoint_doc.allow_guest
        }
        return endpoint_details
    except frappe.DoesNotExistError:
        return None

@frappe.whitelist(methods=["POST", "GET", "PUT", "DELETE"], allow_guest=True)
@log()
def v1(type: str, data: dict | None = None, **kwargs):
    """
    data param is for POST and should be converted to Pydantic Model
    """
    # Fetch endpoint details using the updated get_endpoint_details function
    endpoint = get_endpoint_details(type)

    if not endpoint:
        gen_response(404, "Endpoint not found.")
        return

    if frappe.request.method not in endpoint["methods"]:
        gen_response(405, "Method not allowed.")
        return

    # Check if guest access is allowed for this endpoint
    allow_guest = endpoint.get("allow_guest", False)
    if not allow_guest and frappe.session.user == "Guest":
        gen_response(403, "Guest access not allowed for this endpoint.")
        return

    if not data:
        data = dict()

    # Check if a Pydantic model is specified for this endpoint, if applicable
    model = endpoint.get("model")
    if model:
        data = model(**data)

    try:
        if frappe.request.method == "POST":
            frappe.db.begin()

        # Call the function associated with the endpoint
        function = frappe.get_attr(endpoint["function"])
        result = function(**data) if not model else function(data)

        if frappe.request.method == "POST":
            frappe.db.commit()
    except frappe.AuthenticationError:
        return gen_response(500, frappe.response["message"])
    except Exception as e:
        frappe.log_error(title="Expense Tracker Error", message=frappe.get_traceback())
        result = str(e)
        return gen_response(500, result)
    finally:
        if frappe.request.method == "POST":
            frappe.db.close()

    gen_response(
        200,
        frappe.response["message"],
        result,
    )
    return

def gen_response(status, message, data=None):
    frappe.response["http_status_code"] = status
    if status == 500:
        frappe.response["message"] = BeautifulSoup(str(message)).get_text()
    else:
        frappe.response["message"] = message
    if data is not None:
        frappe.response["data"] = data