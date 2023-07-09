# ZAPPI

## Payload cgi-jstatus-Z

```
{
    'zappi': [
        {
            'batteryDischargeEnabled': False,   // ? V2H support present
            'beingTamperedWith': False,         // ? tamper detection
            'bsm': 1,                           // ?
            'bss': 0,                           // ?
            'bst': 0,                           // ?
            'che': 2.04,                        // Charge added [kWh]
            'cmt': 254,                         // CommandTimer
            'dat': '25-07-2021',                // Current Date
            'div': 5312,                        // Charge rate [W]
            'dst': 1,                           // DaylightSavingsTime
            'ectp1': 5312,                      // CT clamp 1 throughput [W]
            'ectp2': 4924,                      // CT clamp 2 throughput [W]
            'ectp3': 1,                         // CT clamp 3 throughput [W]
            'ectp4': -6,                        // CT clamp 4 throughput [W]
            'ectt1': 'Internal Load',           // CT clamp 1 Name
            'ectt2': 'Grid',                    // CT clamp 2 Name
            'ectt3': 'None',                    // CT clamp 3 Name
            'ectt4': 'None',                    // CT clamp 4 Name
            'ectt5': 'None',                    // CT clamp 5 Name
            'ectt6': 'None',                    // CT clamp 6 Name
            'frq': 49.99,                       // Line Frequency [Hz]
            'fwv': '3560S5.039',                // zappi firmware version
            'g100LockoutState': 'NONE',         // ?
            'gen': 552,                         // Generation rate by PV [W]
            'grd': 4965,                        // Import rate from Grid [W]
            'lck': 31,                          // Lock State %11111
                                                //      b0 = locked now
                                                //      b1 = lock when plugged
                                                //      b2 = lock when unplugged
                                                //      b3 = lock when charging
                                                //      b4 = charge session allowed
            'mgl': 10,                          // Minimum Green Level setting [%]
            'newAppAvailable': False,           // ?
            'newBootloaderAvailable': False,    // ?
            'pha': 1,                           // Number of Phases
            'pri': 1,                           // Priority
            'pst': 'C2',                        // Status
                                                //      A  = EV disconnected
                                                //      B1 = EV connected
                                                //      B2 = Waiting for EV
                                                //      C1 = EV ready to receive charge
                                                //      C2 = Charging
                                                //      F  = Fault
            'pwm': 4100,                        // Pulse Width Modulation [% * 100] 
                                                // percentage of 60A that can be delivered
                                                // 4100 = 24.6 A
            'rac': 4,                           // Residual AC
            'rdc': -4,                          // Residual DC
            'rrac': -8,                         // ?
            'sbh': 17,                          // SmartBoost start time [hr]
            'sbm': 10,                          // SmartBoost start time [min]
            'sbk': 5,                           // SmartBoost energy to add [kWh]
            'sno': ########,                    // Serial Number of zappi
            'sta': 3,                           // Status
                                                //      1 = Paused
                                                //      3 = Charging
                                                //      5 = Complete
            'tbk': 20,                          // Manual boost energy [kWh]
            'tim': '06:30:31',                  // Time (UTC)
            'tz': 3,                            // Timezone
            'vol': 2231,                        // Line Voltage [deciVolt]
            'zmo': 1,                           // zappi Mode
                                                //      0 = Startup/Fault
                                                //      1 = Fast
                                                //      2 = Eco
                                                //      3 = Eco+
                                                //      4 = Stopped
            'zs': 3078,                         // ?
            'zsh': 12,                          // ?
            'zsl': 6,                           // ?
        }
    ]
}
```

## Payload cgi-jdayhour-Z#######-2021-07-25

Note: Energy is in Joules; divide by 60 get average Watts; divide by 3 600 000 to get kWh
```
{
    'U#######': [
        {
            'dom': 25,                  // Day of Month
            'dow': 'Sun',               // Day 0f Week
            'exp': 16560,               // Exported period total [J]
            'frq': 5006,                // Line frequency [centiHertz]
            'gen': 480                  // Energy consumed by inverter (usually at night) [J]
            'gep': 2409600,             // Energy production (solar panels) period total [J] 
            'h1b': 123,                 // Imported energy used for EV period total [J]
            'h1d': 14706420,            // Produced energy diverted to EV (?) period total [J]
            'hr': 6,                    // Hour of the Day (UTC!) (if applicable and non-zero)
            'imp': 13285500,            // Imported period total [J]
            'min': 1,                   // Minute of the Hour (if applicable and non-zero)
            'mon': 7,                   // Month of Year
            'v1': 2446,                 // Line voltage [deciVolt]
            'yr': 2021                  // Year
        },
        #
        truncated
```

`gep` should match hourly PV totaliser   
`imp` imported from grid; should match hourly P1 totaliser (T1,in + T2,in; KAMSTRUP)   
`exp` exported to grid; should match hourly P1 totaliser (T1,out + T2,out; KAMSTRUP)   
`h1d` should match EV consumption
`h1b`: device 1 boost   
`h1d`: device 1 divert   
`h2b`: device 2 boost   
`h2d`: device 2 divert   
