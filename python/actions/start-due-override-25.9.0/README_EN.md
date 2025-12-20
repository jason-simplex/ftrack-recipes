# ftrack Batch Date Editor (Start Due Override)

A powerful ftrack Action plugin for batch editing start and due dates of tasks and milestones, with support for non-working day settings and intelligent date management.

## 🌟 Features

### 1. **Smart Batch Editing**
- Support simultaneous selection of multiple Tasks and Milestones for batch date editing
- Intelligently recognize the current date status of selected entities and automatically display appropriate default values
- Display specific dates when selected entities have the same dates, show blank when different to prompt user input

### 2. **Non-Working Day Support**
- **Break through ftrack default limitations**: Allow setting dates to weekends and holidays
- Not restricted by ftrack work calendar, providing more flexible project scheduling

### 3. **Automatic Project Range Constraints**
- Automatically retrieve project start and end date ranges
- Intelligently limit user input dates within project range to prevent invalid date settings
- Automatically adjust and log when dates exceed project range

### 4. **Special Milestone Handling**
- Automatically identify Milestone entity types
- Intelligently skip Milestone `start_date` assignment (as it's immutable and automatically equals `end_date`)
- Automatically filter Milestone `start_date` in interface display to avoid user confusion

### 5. **Flexible Null Value Handling**
- Support `'null'` value to indicate user doesn't want to set that date field
- Support `'...'` placeholder to indicate multiple different values requiring user input
- Intelligently recognize and maintain null states without invalid assignments

### 6. **User-Friendly Interface**
- Clean and intuitive date selection interface
- Clear labels and prompts
- Smart default value display to reduce user input workload

## 🚀 Usage

### 1. Installation and Deployment
```bash
# Place the script in ftrack's action directory
cp start_due_override.py /path/to/ftrack/actions/

# Or load via ftrack Connect
# Place the entire directory in Connect's plugin directory
```

### 2. Using in ftrack

#### Step 1: Select Entities
- Select one or more Tasks or Milestones in your ftrack project
- You can mix different types of entities

#### Step 2: Launch Action
- Right-click on selected entities
- Choose **"Batch Edit Start/Due Dates"** from the Actions menu

#### Step 3: Review Smart Default Values
- **Same Date Scenario**: If all selected entities have the same date field value, the input box will automatically display that date
- **Different Date Scenario**: If selected entities have different date field values, the input box displays empty, prompting you to enter a new value
- **No Date Scenario**: If entities have no date set, the input box displays empty

#### Step 4: Set Dates
- **Start Date**: Set the start date for tasks (Milestones will be automatically skipped)
- **Due Date**: Set the due date for tasks or milestones
- You can set only one field while keeping the other unchanged

#### Step 5: Confirm Execution
- Click the confirm button to execute batch editing
- The system will automatically handle date constraints and entity type adaptation

### 3. Smart Display Logic Examples

#### Scenario 1: All Entities Have Same Date
```
Selected Entities: Task A (start: January 15, 2025), Task B (start: January 15, 2025)
Interface Display: Start date input box shows "January 15, 2025"
User Action: Can modify to new date or keep unchanged
```

#### Scenario 2: Entities Have Different Dates
```
Selected Entities: Task A (start: January 15, 2025), Task B (start: January 20, 2025)
Interface Display: Start date input box is empty
User Action: Need to input new unified date
```

#### Scenario 3: Mixed Scenario
```
Selected Entities: Task A (start: January 15, 2025), Task B (start: null)
Interface Display: Start date input box is empty
User Action: Input date will be applied to all selected entities
```

### 4. Special Value Handling

| Input Value | Meaning | Processing Method |
|-------------|---------|-------------------|
| `Specific Date` | e.g., `January 15, 2025` | Set to specified date (will be constrained to project range) |
| `Empty Value` | Don't modify this date field | Keep original value unchanged, skip assignment |

### 5. Typical Use Cases

#### Scenario 1: Batch Set Project Milestones
```
Selection: Multiple Milestones
Setting: Due date = March 15, 2025
Result: All milestone due dates are uniformly set, start dates automatically sync
```

#### Scenario 2: Batch Adjust Task Timeline
```
Selection: Multiple Tasks
Setting: Start date = February 01, 2025, Due date = February 28, 2025
Result: All task time ranges are uniformly adjusted
```

#### Scenario 3: Partial Date Adjustment
```
Selection: Multiple Tasks (with different start dates)
Setting: Only set due date = April 30, 2025, leave start date empty
Result: Only due dates are uniformly set, start dates remain original values
```

## ⚙️ Technical Features

### Core Architecture
- Based on `ftrack_action_handler.action.BaseAction`
- Uses ftrack Python API for entity operations
- Supports event-driven asynchronous processing

### Key Technical Highlights
- **Entity Type Adaptation**: Automatically identify and handle special requirements of different entity types
- **Date Format Standardization**: Unified handling of Arrow objects and string formats

### Core Methods
- `_filtered_entities()`: Filter and retrieve Task and Milestone entities
- `_get_smart_date_value()`: Intelligently calculate date display values, returning specific dates, '...' or 'null'
- `_clamp_dates()`: Date range constraints and null value handling
- `launch()`: Execute batch date setting

## 🔧 Configuration

```python
# Action basic information
label = 'Batch Edit Start/Due Dates'
identifier = 'com.tiger.start_due_override'
description = 'Dates can be set to non-working days'
icon = 'https://pipedream.com/s.v0/app_13Gh2V/logo/orig'
```

## 🆚 Comparison with Default Features

| Feature | ftrack Default | This Plugin |
|---------|----------------|-------------|
| Non-working Day Setting | ❌ Not Supported | ✅ Fully Supported |
| Batch Editing | ⚠️ Limited Support | ✅ Smart Batch Editing |
| Milestone Handling | ⚠️ Error-prone | ✅ Smart Recognition and Handling |
| Date Constraints | ❌ Manual Check | ✅ Automatic Project Range Constraints |
| Null Value Handling | ⚠️ Basic Support | ✅ Flexible Null Value Strategy |

## ⚠️ Notes

1. **Milestone Limitations**: Milestone `start_date` is immutable, the system will automatically skip it
2. **Project Range**: All dates will be automatically constrained within the project's start and end date range
3. **Permission Requirements**: Edit permissions are required for selected entities

## 🔄 Version Updates

### Latest Version Features
- ✅ Optimized interface display logic
- ✅ Enhanced error handling and logging
- ✅ Improved date range constraint functionality

## 🤝 Contributing

Welcome to submit Issues and Pull Requests to improve this plugin!

## 📄 License

This project follows ftrack's license terms.