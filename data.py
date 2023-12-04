from neo4j import GraphDatabase

uri = "bolt://localhost:7687"
username = "neo4j"
password = "test1234"
driver = GraphDatabase.driver(uri, auth=(username, password), database="neo4j")

employees_data = [
    {
        "id": 1,
        "firstname": "John",
        "lastname": "Doe",
        "position": "Manager",
        "department": "HR",
    },
    {
        "id": 2,
        "firstname": "Jane",
        "lastname": "Smith",
        "position": "Developer",
        "department": "IT",
    },
    {
        "id": 3,
        "firstname": "Bob",
        "lastname": "Johnson",
        "position": "Analyst",
        "department": "Finance",
    },
    {
        "id": 4,
        "firstname": "Alice",
        "lastname": "White",
        "position": "Manager",
        "department": "IT",
    },
    {
        "id": 5,
        "firstname": "Charlie",
        "lastname": "Brown",
        "position": "Developer",
        "department": "IT",
    },
    {
        "id": 6,
        "firstname": "Eva",
        "lastname": "Green",
        "position": "Analyst",
        "department": "Finance",
    },
]

departments_data = [
    {"name": "HR", "manager_id": 1},
    {"name": "IT", "manager_id": 4},
    {"name": "Finance", "manager_id": 3},
]


def create_sample_data(tx):
    for employee in employees_data:
        tx.run(
            "CREATE (e:Employee {id: $id, firstname: $firstname, lastname: $lastname, position: $position, department: $department})",
            **employee,
        )

    for department in departments_data:
        tx.run(
            "CREATE (d:Department {name: $name}) "
            "WITH d "
            "MATCH (e:Employee {id: $manager_id}) "
            "CREATE (e)-[:MANAGES]->(d)",
            **department,
        )

    for employee_id, department_name in [
        (1, "HR"),
        (2, "IT"),
        (3, "Finance"),
        (4, "IT"),
        (5, "IT"),
        (6, "Finance"),
    ]:
        tx.run(
            "MATCH (e:Employee {id: $employee_id}), (d:Department {name: $department_name}) "
            "CREATE (e)-[:WORKS_IN]->(d)",
            employee_id=employee_id,
            department_name=department_name,
        )


with driver.session() as session:
    try:
        session.write_transaction(create_sample_data)
        print("Przykładowe dane utworzone pomyślnie.")
    except Exception as e:
        print(f"Błąd podczas tworzenia przykładowych danych: {e}")
        raise e
