# SolarEgeAPI ComponentType.CONNECTOR

## Version: 1.0.0

## Table of Contents  
1. [Description](#description)
2. [Input](#Input)
3. [Output](#Output)
4. [Bindings](#Bindings)

### Description

This component serves as a connector to Solar Edge API. It allows to get site data such as power and energy, as well as inverters specific data, to be saved to Splight Platform.

### Input

The component's input parameters are:

- api_key [str]: (Default: IFLVQCO7M6I9TVU4R2HW60LLZ1YWY9FK) 
- request_period [int]: (Default: 600) 


### Custom Types

The custom types defined by the component are:

- SiteReader
     asset [Asset]: (Default: ) 
     attribute [Attribute]: (Default: ) 
     resource [str]: (Default: ) 
     site_id [str]: (Default: ) 
     
- InverterReader
     asset [Asset]: (Default: ) 
     attribute [Attribute]: (Default: ) 
     resource [str]: (Default: ) 
     site_id [str]: (Default: ) 
     serial_number [str]: (Default: ) 
     
### Output

The component's output are:

### Bindings

1. handle_site_reader_create: The binding **handle_site_reader_create** is executed when the action **CREATE** is applied on a **SiteReader**.
2. handle_site_reader_delete: The binding **handle_site_reader_delete** is executed when the action **DELETE** is applied on a **SiteReader**.
3. handle_inverter_reader_create: The binding **handle_inverter_reader_create** is executed when the action **CREATE** is applied on a **InverterReader**.
4. handle_inverter_reader_delete: The binding **handle_inverter_reader_delete** is executed when the action **DELETE** is applied on a **InverterReader**.


### Commands

This component does not have any command.### Endpoints

This component does not have any endpoint