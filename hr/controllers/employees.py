""" This is the controller of the /employees endpoint

The following functions are called from here: GET, POST, PATCH, and DELETE.
"""
import json
import os
from datetime import datetime
from random import randrange
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import exists, and_
from databasesetup import create_session, Employee, Salary, Address, Title, Department
from helpers.db_object_helper import \
    get_all_children_objects, get_active_address, \
    get_active_title, get_active_department, get_active_salary
from helpers.regex_helper import validate_address
from models.employee_api_model import EmployeeApiModel
from models.employee_response import EmployeeResponse
import logging

logging.basicConfig(filename='./log.txt', format='%(asctime)s :: %(name)s :: %(message)s')
logger = logging.getLogger(__name__)


def get(employee_id=None, static_flag=False, session=None):
    """ This is the GET function that will return one or more employee objects within the system.
    :param employee_id:
    :param static_flag:
    :return: a set of Employee Objects
    """
    if static_flag:
        logger.warning("Get Employees - Loading static file.")
        scriptdir = '/'.join(os.path.dirname(os.path.abspath(__file__)).split('/')[:-2])
        sp_file = os.path.join(scriptdir, 'static/dummy.txt')
        obj = json.load(open(sp_file))

        if employee_id is not None and employee_id[0] < 3:
            return obj["employee_array"][employee_id[0]-1]
        return obj["employee_array"]

    if session is None:
        session = create_session()
    employee_collection = []
    info = "Get Employees - Found the following employees - "

    if employee_id is None:
        try:
            if not session.query(Employee).first():
                session.rollback()
                logger.warning("Get Employees - No employees exist in the system")
                return {'error message': 'No employees exist in the system'}, 400

            all_employee_objects = session.query(Employee).all()

            for employee_object in all_employee_objects:
                children = get_all_children_objects(employee_object)
                employee = EmployeeApiModel(is_active=employee_object.is_active,
                                            employee_id=employee_object.id,
                                            name=employee_object.first_name + ' ' + employee_object.last_name,
                                            birth_date=employee_object.birth_date,
                                            email=employee_object.email,
                                            address=children['address'].to_str(),
                                            department=children['department'].to_str(),
                                            role=children['title'].to_str(),
                                            team_start_date=children['department'].start_date,
                                            start_date=employee_object.start_date,
                                            salary=children['salary'].to_str())
                employee_collection.append(employee)

        except SQLAlchemyError:
            session.rollback()
            error_message = 'Error while retrieving all employees'
            logger.warning("Employees.py Get - " + error_message)
            return {'error_message': error_message}, 400

    else:
        for e_id in employee_id:
            try:
                if not session.query(exists().where(Employee.id == e_id)).scalar():
                    session.rollback()
                    error_message = 'An employee with the id of %s does not exist' % e_id
                    logger.warning("Get Employees - " + error_message)
                    return {'error message': error_message}, 400

                employee_object = session.query(Employee).get(e_id)
                children = get_all_children_objects(employee_object)
                employee = EmployeeApiModel(is_active=employee_object.is_active,
                                            employee_id=employee_object.id,
                                            name=employee_object.first_name + ' ' + employee_object.last_name,
                                            birth_date=employee_object.birth_date,
                                            email=employee_object.email,
                                            address=children['address'].to_str(),
                                            department=children['department'].to_str(),
                                            role=children['title'].to_str(),
                                            team_start_date=children['department'].start_date,
                                            start_date=employee_object.start_date,
                                            salary=children['salary'].to_str())
                employee_collection.append(employee)
                info += "Employee ID: %s, Name: %s, Email: %s, Birth date: %s, Department: %s, Role: %s " % \
                        (employee_object.id,
                         employee_object.first_name + ' ' + employee_object.last_name,
                         employee_object.email,
                         employee_object.birth_date,
                         children['department'].to_str(),
                         children['title'].to_str())

            except SQLAlchemyError:
                session.rollback()
                error_message = 'Error while retrieving employee %s' % employee_id
                logger.warning("Employees.py Get - " + error_message)
                return {'error_message': error_message}, 400

    # CLOSE
    session.close()
    logger.warning(info)
    return EmployeeResponse(employee_collection).to_dict()


def post(employee, session=None):
    """
    :param employee:
    :return:
    """
    if session is None:
        session = create_session()

    # ADD EMPLOYEE
    try:
        # Check if Employee Already exists
        if session.query(exists().where(and_(
                Employee.first_name == employee['fname'],
                Employee.last_name == employee['lname'],
                Employee.email == employee['email'],
                Employee.birth_date == datetime.strptime(employee['birth_date'], '%Y-%m-%d').date(),
                Employee.start_date == datetime.strptime(employee['start_date'], '%Y-%m-%d').date()))).scalar():
            session.rollback()
            logger.warning("The following employee was attempted to add with POST but already exists. "
                           "Please use PATCH to modify the employee's data or enter a new employee. "
                           "A new employee has a unique first name, last name, birth date, and start date. "
                           "Employee Name: %s, Birth Date: %s, Start Date: %s." %
                           (employee['fname'] + ' ' + employee['lname'],
                            employee['birth_date'],
                            employee['start_date']))
            return {'error_message':
                    'This employee already exists in the system. Please use PATCH to modify them or enter a new '
                    'employee. A new employee has a unique first name, last name, birth date, and start date'}, 400

        birthday = datetime.strptime(employee['birth_date'], '%Y-%m-%d').date()  # e.g. 1993-12-17
        start_date = datetime.strptime(employee['start_date'], '%Y-%m-%d').date()  # e.g. 2017-03-28
        if employee['is_active']:
            logger.warning("The start date input (%s) is greater than today's date, but the employee is said to be "
                           "active. So the start date for the employee is marked as now. To change either of these "
                           "things, Use PATCH", start_date)
            start_date = datetime.now()
        new_employee = Employee(is_active=employee['is_active'], first_name=employee['fname'],
                                last_name=employee['lname'], birth_date=birthday, email=employee['email'],
                                phones=0, orders=0, start_date=start_date)
        session.add(new_employee)
    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while importing employee base'
        logger.warning("Employees.py Post - " + error_message +
                       ". Unable to add the following employee: "
                       "Employee Name: %s, Birth Date: %s, Start Date: %s." %
                       (employee['fname'] + ' ' + employee['lname'],
                        employee['birth_date'],
                        employee['start_date']))
        return {'error_message': error_message}, 400

    # ADD ADDRESS
    # Use regex to check that the format is "0200 StreetAddress St., City, State 11111"
    try:
        address = validate_address(employee['address'])
        address_date = datetime.strptime(employee['start_date'], '%Y-%m-%d').date()  # e.g. 2017-03-28
        session.add(Address(is_active=True, street_address=address['street_address'], city=address['city'],
                            state=address['state'], zip=address['zip'], start_date=address_date, employee=new_employee))
    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while importing employee address'
        logger.warning("Employees.py Post - " + error_message +
                       ". Unable to add the address for the following employee: "
                       "Employee Name: %s, Birth Date: %s, Start Date: %s." %
                       (employee['fname'] + ' ' + employee['lname'],
                        employee['birth_date'],
                        employee['start_date']))
        return {'error_message': error_message}, 400

    # ADD DEPARTMENT
    try:
        department_start_date = datetime.strptime(employee['start_date'], '%Y-%m-%d').date()  # e.g. 2017-03-28
        session.add(Department(is_active=True, start_date=department_start_date, name=employee['department'],
                               employee=new_employee))
    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while importing employee department'
        logger.warning("Employees.py Post - " + error_message +
                       ". Unable to add the department and role for the following employee: "
                       "Employee Name: %s, Birth Date: %s, Start Date: %s." %
                       (employee['fname'] + ' ' + employee['lname'],
                        employee['birth_date'],
                        employee['start_date']))
        return {'error_message': error_message}, 400

    # ADD TITLE
    # Note: This should be the same as the team_start_date for POST'ing a new employee
    try:
        session.add(Title(is_active=True, name=employee['role'], start_date=department_start_date,
                          employee=new_employee))
    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while importing employee title'
        logger.warning("Employees.py Post - " + error_message +
                       ". Unable to add the position title for the following employee: "
                       "Employee Name: %s, Birth Date: %s, Start Date: %s." %
                       (employee['fname'] + ' ' + employee['lname'],
                        employee['birth_date'],
                        employee['start_date']))
        return {'error_message': error_message}, 400

    # ADD SALARY
    try:
        session.add(Salary(is_active=True, amount=randrange(50000, 100000, 1000), employee=new_employee))
    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while importing employee salary'
        logger.warning("Employees.py Post - " + error_message +
                       ". Unable to add the salary for the following employee: "
                       "Employee Name: %s, Birth Date: %s, Start Date: %s." %
                       (employee['fname'] + ' ' + employee['lname'],
                        employee['birth_date'],
                        employee['start_date']))
        return {'error_message': error_message}, 400

    # COMMIT & CLOSE
    session.commit()
    session.close()

    return {'employee': employee}, 200


def patch(employee, session=None):
    """
    :param employee:
    :return:
    """
    if session is None:
        session = create_session()

    try:
        # Check if Employee exists
        if not session.query(exists().where(Employee.id == employee['employee_id'])).scalar():
            error_message = 'This employee does not exist in the system yet. ' \
                           'Please use POST to add them as a new employee'
            logger.warning("Employees.py Patch - "
                           "The following employee does not exist in the system" +
                           "Employee ID: {0}.".format(employee['employee_id']))
            return {'error_message': error_message}, 400

        employee_object = session.query(Employee).get(employee['employee_id'])

        old_employee = 'Employee ID: %s, Name: %s, Birth Date: %s, Start Date: %s,' \
                       ' Email: %s, Active Status: %s' \
                       % (employee_object.id,
                          employee_object.first_name + ' ' + employee_object.last_name,
                          employee_object.birth_date,
                          employee_object.start_date,
                          employee_object.email,
                          employee_object.is_active)

        # MODIFY EMPLOYEE
        if 'is_active' in employee:
            employee_object.is_active = employee['is_active']
        if 'fname' in employee:
            employee_object.first_name = employee['fname']
        if 'lname' in employee:
            employee_object.last_name = employee['lname']
        if 'email' in employee:
            employee_object.email = employee['email']
        if 'birth_date' in employee:
            employee_object.birth_date = datetime.strptime(employee['birth_date'], '%Y-%m-%d').date()
        if 'start_date' in employee:
            employee_object.start_date = datetime.strptime(employee['start_date'], '%Y-%m-%d').date()

    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while modifying employee base'
        logger.warning("Employees.py Patch - "
                       "Error while modifying the employee %s", employee['employee_id'])
        return {'error_message': error_message}, 400

    # MODIFY ADDRESS
    try:
        if 'address' or 'address_start_date' in employee:
            address_object = get_active_address(employee_object)

            if 'address_start_date' in employee and 'address' not in employee:
                address_object.start_date = datetime.strptime(employee['address_start_date'], '%Y-%m-%d').date()

            elif 'address' in employee and 'address_start_date' not in employee:
                address = validate_address(employee['address'])
                address_object.is_active = False
                now_date = datetime.strptime(str(datetime.now().year) + '-' +
                                             str(datetime.now().month) + '-' +
                                             str(datetime.now().day), '%Y-%m-%d').date()
                session.add(Address(is_active=True, street_address=address['street_address'], city=address['city'],
                                    state=address['state'], zip=address['zip'], employee=employee_object,
                                    start_date=now_date))

            elif 'address' in employee and 'address_start_date' in employee:
                address = validate_address(employee['address'])
                address_object.is_active = False
                start_date = datetime.strptime(employee['address_start_date'], '%Y-%m-%d').date()
                session.add(Address(is_active=True, street_address=address['street_address'], city=address['city'],
                                    state=address['state'], zip=address['zip'], employee=employee_object,
                                    start_date=start_date))

    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while modifying employee address'
        logger.warning("Employees.py Patch - " 
                       "Error while modifying the address for the employee %s", employee['employee_id'])
        return {'error_message': error_message}, 400

    # MODIFY SALARY
    try:

        if 'salary' in employee:
            salary_object = get_active_salary(employee_object)
            salary_object.is_active = False
            session.add(Salary(is_active=True, amount=employee['salary'], employee=employee_object))
    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while modifying employee salary'
        logger.warning("Employees.py Patch - "
                       "Error while modifying the salary for the employee %s", employee['employee_id'])
        return {'error_message': error_message}, 400

    # MODIFY TITLE
    try:
        if 'role' or 'role_start_date' in employee:
            title_object = get_active_title(employee_object)

            if 'role_start_date' in employee and 'role' not in employee:
                title_object.start_date = datetime.strptime(employee['role_start_date'], '%Y-%m-%d').date()

            elif 'role' in employee and 'role_start_date' not in employee:
                title_object.is_active = False
                now_date = datetime.strptime(str(datetime.now().year) + '-' +
                                             str(datetime.now().month) + '-' +
                                             str(datetime.now().day), '%Y-%m-%d').date()
                session.add(Title(is_active=True, name=employee['role'], start_date=now_date,
                                  employee=employee_object))

            elif 'role' in employee and 'role_start_date' in employee:
                title_object.is_active = False
                start_date = datetime.strptime(employee['role_start_date'], '%Y-%m-%d').date()
                session.add(Title(is_active=True, name=employee['role'], start_date=start_date,
                                  employee=employee_object))

    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while modifying employee role & title'
        logger.warning("Emplyees.py Patch - "
                       "Error while modifying the role/title for the employee %s", employee['employee_id'])
        return {'error_message': error_message}, 400

    # MODIFY DEPARTMENT
    try:
        if 'department' or 'department_start_date' in employee:
            department_object = get_active_department(employee_object)

            if 'department_start_date' in employee and 'department' not in employee:
                department_object.start_date = datetime.strptime(employee['department_start_date'], '%Y-%m-%d').date()

            elif 'department' in employee and 'department_start_date' not in employee:
                department_object.is_active = False
                now_date = datetime.strptime(str(datetime.now().year) + '-' +
                                             str(datetime.now().month) + '-' +
                                             str(datetime.now().day), '%Y-%m-%d').date()
                session.add(Department(is_active=True, name=employee['department'], start_date=now_date,
                                       employee=employee_object))

            elif 'department' in employee and 'department_start_date' in employee:
                department_object.is_active = False
                start_date = datetime.strptime(employee['department_start_date'], '%Y-%m-%d').date()
                session.add(Department(is_active=True, name=employee['department'], start_date=start_date,
                                       employee=employee_object))

    except SQLAlchemyError:
        session.rollback()
        error_message = 'Error while modifying employee department & team'
        logger.warning("Employees.py Patch - " 
                       "Error while modifying the department for the employee %s", employee['employee_id'])
        return {'error_message': error_message}, 400

    new_employee = 'Employee ID: %s, Name: %s, Birth Date: %s, Start Date: %s,' \
                   ' Email: %s, Active Status: %s' \
                   % (employee_object.id,
                      employee_object.first_name + ' ' + employee_object.last_name,
                      employee_object.birth_date,
                      employee_object.start_date,
                      employee_object.email,
                      employee_object.is_active)

    # COMMIT & CLOSE
    session.commit()
    session.close()

    logger.warning('Successfully modified an employee. Old information: '
                   + old_employee + " New information: " + new_employee)
    return {'new_employee': employee}, 200


def delete(employee_id, session=None):
    """
    :param employee_id:
    :return:
    """
    if session is None:
        session = create_session()

    try:
        if not session.query(exists().where(Employee.id == employee_id)).scalar():
            session.rollback()
            return {'error message': 'An employee with the id of %s does not exist' % employee_id}, 400
        employee = get(employee_id=[employee_id],session=session)['employee_array'][0]
        session.query(Employee).filter_by(id=employee_id).delete()
    except SQLAlchemyError:
        session.rollback()
        error_message = "Error while deleting employee %s" % employee_id
        logger.warning("Employees.py - " + error_message)
        return {'error_message': error_message}, 400

    # COMMIT & CLOSE
    logger.warning("Successfully deleted the following employee: "
                   "Employee ID: %s, Name %s, Birth Date %s, Department: %s"
                   % (employee['employee_id'],
                      employee['name'],
                      datetime.strptime(str(employee['birth_date']), '%Y-%m-%d').date(),
                      employee['department']))

    session.commit()
    session.close()
    return {'deleted_employee': employee}, 200
