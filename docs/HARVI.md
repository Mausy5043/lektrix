# HARVI

## Payload cgi-jstatus-H...
Call: `https://s__.myenergi.net/cgi-jstatus-H########`   

Where:
* `s__` is the server-id
* `########` is the 8-digit serialnumber of your HARVI.

```
{
    'harvi': [
        {
            'dat': '25-07-2021',            // Date
            'ect1p': 1,                     // Physical CT clamp 1 used [0/1]
            'ect2p': 1,                     // Physical CT clamp 2 used [0/1]
            'ect3p': 1,                     // Physical CT clamp 3 used [0/1]
            'ectp1': 1097,                  // Physical CT clamp 1 throughput [W]
            'ectp2': 0,                     // Physical CT clamp 2 throughput [W]
            'ectp3': 0,                     // Physical CT clamp 3 throughput [W]
            'ectt1': 'Generation',          // Physical CT clamp 1 Name
            'ectt2': 'None',                // Physical CT clamp 2 Name
            'ectt3': 'None',                // Physical CT clamp 3 Name
            'fwv': '3170S0.000',            // Firmware Version
            'sno': xxxxxxxx,                // Serial Number of Harvi
            'tim': '07:44:08'               // Time (UTC)
        }
    ]
}

```
