from flask import Flask, request, jsonify
from neo4j import GraphDatabase

# from dotenv import load_dotenv
# import os

# load_dotenv()

app = Flask(__name__)

# uri = os.getenv("URI")
# username = os.getenv("USERNAME")
# password = os.getenv("PASSWORD")

uri = "bolt://localhost:7687"
username = "neo4j"
password = "test1234"
driver = GraphDatabase.driver(uri, auth=(username, password), database="neo4j")


# 3 punkt
def get_employees(tx, position_name=None, sort_by=None):
    query = "MATCH (e:Employee) "

    if position_name:
        query += "WHERE toLower(e.position) CONTAINS toLower($position_name) "

    query += "RETURN ID(e) AS id, e.firstname AS firstname, e.lastname AS lastname, e.position AS position, e.department AS department "

    if sort_by:
        query += f"ORDER BY {sort_by}"

    results = tx.run(query, position_name=position_name, sort_by=sort_by).data()
    employees = [
        {
            "id": result["id"],
            "firstname": result["firstname"],
            "lastname": result["lastname"],
            "position": result["position"],
            "department": result["department"],
        }
        for result in results
    ]
    return employees


@app.route("/employees", methods=["GET"])
def get_employees_route():
    try:
        position_name = request.args.get("filter_name")
        sort_by = request.args.get("sort_by")

        with driver.session() as session:
            employees = session.read_transaction(get_employees, position_name, sort_by)

        return jsonify(employees), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 4 punkt
def employee_exists(tx, firstname, lastname):
    query = "MATCH (e:Employee) WHERE e.firstname = $firstname AND e.lastname = $lastname RETURN COUNT(e) AS count"
    result = tx.run(query, firstname=firstname, lastname=lastname).single()
    return result["count"] > 0


def add_employee(tx, firstname, lastname, position, department):
    query_create_employee = "CREATE (e:Employee {firstname: $firstname, lastname: $lastname, position: $position, department: $department})"
    query_create_relationship_works_in = (
        "MATCH (e:Employee {firstname: $firstname, lastname: $lastname}), (d:Department {name: $department}) "
        "CREATE (e)-[:WORKS_IN]->(d)"
    )
    query_create_relationship_manages = (
        "MATCH (e:Employee {firstname: $firstname, lastname: $lastname}), (d:Department {name: $department}) "
        "CREATE (e)-[:MANAGES]->(d)"
    )

    tx.run(
        query_create_employee,
        firstname=firstname,
        lastname=lastname,
        position=position,
        department=department,
    )
    tx.run(
        query_create_relationship_works_in,
        firstname=firstname,
        lastname=lastname,
        department=department,
    )

    if position.lower() == "manager":
        tx.run(
            query_create_relationship_manages,
            firstname=firstname,
            lastname=lastname,
            department=department,
        )


@app.route("/employees", methods=["POST"])
def add_employee_route():
    data = request.get_json()

    if (
        "firstname" not in data
        or "lastname" not in data
        or "position" not in data
        or "department" not in data
    ):
        return (
            jsonify(
                {
                    "error": "Nie podano wszystkich danych (imię, nazwisko, stanowisko, departament)"
                }
            ),
            400,
        )

    firstname = data["firstname"]
    lastname = data["lastname"]
    position = data["position"]
    department = data["department"]

    try:
        with driver.session() as session:
            if session.read_transaction(employee_exists, firstname, lastname):
                return (
                    jsonify(
                        {
                            "error": "Użytkownik o podanym imieniu i nazwisku już istnieje"
                        }
                    ),
                    400,
                )

            session.write_transaction(
                add_employee, firstname, lastname, position, department
            )

        return jsonify({"message": "Użytkownik dodany"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 5 punkt
def update_employee(tx, id, new_firstname, new_lastname, new_position, new_department):
    query_update_employee = (
        "MATCH (e:Employee) WHERE ID(e) = $id "
        "SET e.firstname = $new_firstname, e.lastname = $new_lastname, e.position = $new_position, e.department = $new_department"
    )
    tx.run(
        query_update_employee,
        id=id,
        new_firstname=new_firstname,
        new_lastname=new_lastname,
        new_position=new_position,
        new_department=new_department,
    )

    query_delete_relations = (
        "MATCH (e:Employee)-[r:WORKS_IN|MANAGES]->() " "WHERE ID(e) = $id DELETE r"
    )
    tx.run(query_delete_relations, id=id)

    query_create_relationship_works_in = (
        "MATCH (e:Employee) WHERE ID(e) = $id "
        "MATCH (d:Department {name: $new_department}) "
        "CREATE (e)-[:WORKS_IN]->(d)"
    )
    tx.run(query_create_relationship_works_in, id=id, new_department=new_department)

    if new_position.lower() == "manager":
        query_create_relationship_manages = (
            "MATCH (e:Employee) WHERE ID(e) = $id "
            "MATCH (d:Department {name: $new_department}) "
            "CREATE (e)-[:MANAGES]->(d)"
        )
        tx.run(query_create_relationship_manages, id=id, new_department=new_department)


@app.route("/employees/<int:id>", methods=["PUT"])
def update_employee_route(id):
    data = request.get_json()

    with driver.session() as session:
        employee_exists_query = (
            "MATCH (e:Employee) WHERE ID(e) = $id RETURN COUNT(e) AS count"
        )
        result = session.run(employee_exists_query, id=id).single()

        if result["count"] == 0:
            return (
                jsonify({"error": "Pracownik o podanym identyfikatorze nie istnieje"}),
                404,
            )

    new_firstname = data.get("firstname")
    new_lastname = data.get("lastname")
    new_position = data.get("position")
    new_department = data.get("department")

    if (
        "firstname" not in data
        or "lastname" not in data
        or "position" not in data
        or "department" not in data
    ):
        return (
            jsonify(
                {
                    "error": "Nie podano wszystkich danych (imię, nazwisko, stanowisko, departament)"
                }
            ),
            400,
        )

    try:
        with driver.session() as session:
            session.write_transaction(
                update_employee,
                id,
                new_firstname,
                new_lastname,
                new_position,
                new_department,
            )
            return jsonify({"message": "Dane pracownika zaktualizowane pomyślnie"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 6 punkt
def delete_employee(tx, id):
    check_manager_query = (
        "MATCH (e:Employee)-[:MANAGES]->(d:Department) "
        "WHERE ID(e) = $id "
        "RETURN ID(d) AS department_id"
    )
    department_id = tx.run(check_manager_query, id=id).single()

    delete_employee_query = "MATCH (e:Employee) WHERE ID(e) = $id DETACH DELETE e"
    tx.run(delete_employee_query, id=id)

    if department_id:
        department_id = department_id["department_id"]
        find_new_manager_query = (
            "MATCH (d:Department)<-[:MANAGES]-(e:Employee) "
            "WHERE ID(d) = $department_id "
            "RETURN e ORDER BY ID(e) LIMIT 1"
        )
        new_manager = tx.run(
            find_new_manager_query, department_id=department_id
        ).single()

        if new_manager is None:
            delete_department_query = (
                "MATCH (d:Department) WHERE ID(d) = $department_id DETACH DELETE d"
            )
            tx.run(delete_department_query, department_id=department_id)


@app.route("/employees/<int:id>", methods=["DELETE"])
def delete_employee_route(id):
    with driver.session() as session:
        employee_exists_query = (
            "MATCH (e:Employee) WHERE ID(e) = $id RETURN COUNT(e) AS count"
        )
        result = session.run(employee_exists_query, id=id).single()

        if result["count"] == 0:
            return (
                jsonify({"error": "Pracownik o podanym identyfikatorze nie istnieje"}),
                404,
            )

        try:
            session.write_transaction(delete_employee, id)
            return jsonify({"message": "Pracownik usunięty pomyślnie"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


# 7 punkt
def get_subordinates(tx, id):
    query = (
        "MATCH (manager:Employee)-[:MANAGES]->(department:Department) "
        "WHERE ID(manager) = $id "
        "WITH department, manager "
        "MATCH (subordinate:Employee)-[:WORKS_IN]->(department) "
        "WHERE ID(subordinate) <> ID(manager) "
        "RETURN subordinate.firstname AS firstname, subordinate.lastname AS lastname, subordinate.position AS position, subordinate.department AS department "
    )
    results = tx.run(query, id=id).data()

    subordinates = [
        {
            "firstname": result["firstname"],
            "lastname": result["lastname"],
            "position": result["position"],
            "department": result["department"],
        }
        for result in results
    ]
    return subordinates


@app.route("/employees/<int:id>/subordinates", methods=["GET"])
def get_subordinates_route(id):
    with driver.session() as session:
        employee_exists_query = (
            "MATCH (e:Employee) WHERE ID(e) = $id RETURN COUNT(e) AS count"
        )
        result = session.run(employee_exists_query, id=id).single()

        if result["count"] == 0:
            return (
                jsonify({"error": "Pracownik o podanym identyfikatorze nie istnieje"}),
                404,
            )

        try:
            subordinates = session.read_transaction(get_subordinates, id)
            return jsonify(subordinates), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


# 8 punkt
def get_employee_department(tx, id):
    query = (
        "MATCH (e:Employee)-[:WORKS_IN]->(d:Department) "
        "WHERE ID(e) = $id "
        "RETURN d.name AS department_name"
    )
    result = tx.run(query, id=id).single()

    if not result:
        return None

    department_name = result["department_name"]

    department_details_query = (
        "MATCH (e:Employee)-[:WORKS_IN]->(d:Department)<-[:MANAGES]-(m:Employee) "
        "WHERE d.name = $department_name "
        "RETURN d.name AS department_name, COUNT(e) AS num_employees, m.firstname, m.lastname"
    )
    department_details = tx.run(
        department_details_query, department_name=department_name
    ).single()

    return {
        "department_name": department_details["department_name"],
        "num_employees": department_details["num_employees"],
        "manager_firstname": department_details["m.firstname"],
        "manager_lastname": department_details["m.lastname"],
    }


@app.route("/employees/<int:id>/department", methods=["GET"])
def get_employee_department_route(id):
    with driver.session() as session:
        employee_exists_query = (
            "MATCH (e:Employee) WHERE ID(e) = $id RETURN COUNT(e) AS count"
        )
        result = session.run(employee_exists_query, id=id).single()

        if result["count"] == 0:
            return (
                jsonify({"error": "Pracownik o podanym identyfikatorze nie istnieje"}),
                404,
            )

        try:
            department_info = session.read_transaction(get_employee_department, id)
            if not department_info:
                return (
                    jsonify(
                        {
                            "error": "Pracownik nie jest przypisany do żadnego departamentu"
                        }
                    ),
                    404,
                )

            return jsonify(department_info), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500


# 9 punkt
def get_departments(tx, department_name=None, sort_by=None):
    query = (
        "MATCH (d:Department) "
        "OPTIONAL MATCH (d)<-[:WORKS_IN]-(e:Employee) "
        "WITH d, COUNT(e) AS num_employees "
    )

    if department_name:
        query += "WHERE toLower(d.name) CONTAINS toLower($department_name) "

    query += "RETURN d.name AS department_name, num_employees "

    if sort_by:
        query += f"ORDER BY {sort_by}"

    results = tx.run(query, department_name=department_name, sort_by=sort_by)

    departments = [
        {
            "department_name": result["department_name"],
            "num_employees": result["num_employees"],
        }
        for result in results
    ]
    return departments


@app.route("/departments", methods=["GET"])
def get_departments_route():
    try:
        department_name = request.args.get("department_name")
        sort_by = request.args.get("sort_by")

        with driver.session() as session:
            departments = session.read_transaction(
                get_departments, department_name, sort_by
            )

        return jsonify(departments), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 10 punkt
def get_department_employees(tx, department_id):
    query = (
        "MATCH (e:Employee)-[:WORKS_IN]->(d:Department) "
        "WHERE ID(d) = $department_id "
        "RETURN e.firstname AS firstname, e.lastname AS lastname, e.position AS position, e.department AS department"
    )

    results = tx.run(query, department_id=department_id)

    employees = [
        {
            "firstname": result["firstname"],
            "lastname": result["lastname"],
            "position": result["position"],
            "department": result["department"],
        }
        for result in results
    ]
    return employees


@app.route("/departments/<int:id>/employees", methods=["GET"])
def get_department_employees_route(id):
    try:
        with driver.session() as session:
            employees = session.read_transaction(
                get_department_employees, department_id=id
            )

        return jsonify(employees), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
