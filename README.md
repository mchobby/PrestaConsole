This project contains some code around the PrestaShop API in Python.

The aim of this project is to help in createing administrative tools around an existing PrestaShop Installation.
Only reads the Prestashop API, NO WRITES!

# Discover the PrestaShop API.

You must first activate the WebService on your shop and generate an API KEY. This API will be used to authenticate the user web session. After, you can simply query you API with directly from a WebBrowser (it issue GET request on the API)

Please see this PDF file for more information about how to activate the API:
* doc.prestashop.com/download/attachments/327702/CRUD+Tutorial+FR.pdf 

Then you can issue your first API Call (which list the authorized API call)
* http://your-api-key@www.myprestashop.be/api/

Once you session is opened with the web browser, you can issue others api call with simplifier url
* http://www.myprestashop.be/api/customers/100/

The API also allows you to restrict the displayed items
* https://www.myprestashop.be/api/products?display=[id,reference,active,name,price,wholesale_price,id_supplier,id_category_default,advanced_stock_management,available_for_order,ean13]

#  Installation 
To use those snip of code, you will need your own "config.ini" file.
You can create if from the config-sample.ini explaining the expected information.

some scripts (eg: label-print.py) relies on a PCL generator python code.
The code is stored within the PythonPCL GitHub available at:
  https://github.com/mchobby/PythonPcl.git
If the script tries to load it but the code is not available then you get the error message:

ImportError: No module named pypcl

What I'm usually doing:
* git clone https://github.com/mchobby/PythonPcl.git
* create a symbolic link pypcl in PrestaConsole to the target the pypcl code.
```cd PrestaConsole
ln -s ./../PythonPcl/pypcl pypcl``` 

# Remarks

**STILL UNDER DEVELOPMENT**

This code is stable but still buggy.

# GNU Licence
This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.
  
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
  
You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
MA 02110-1301, USA. 
