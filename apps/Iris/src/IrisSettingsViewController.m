// IrisSettingsViewController.m - Application settings and HakiOS performance diagnostics
#import "IrisSettingsViewController.h"
#import "IrisTheme.h"

@interface IrisSettingsViewController () <UITableViewDataSource, UITableViewDelegate>

@property (nonatomic, strong) UITableView *tableView;
@property (nonatomic, strong) UISwitch *themeSwitch;

@end

@implementation IrisSettingsViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"Settings";
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    self.navigationItem.rightBarButtonItem = [[UIBarButtonItem alloc] initWithTitle:@"Done"
                                                                              style:UIBarButtonItemStyleDone
                                                                             target:self
                                                                             action:@selector(dismissSelf)];
    
    self.tableView = [[UITableView alloc] initWithFrame:self.view.bounds style:UITableViewStyleGrouped];
    self.tableView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.tableView.backgroundColor = [UIColor clearColor];
    self.tableView.dataSource = self;
    self.tableView.delegate = self;
    [self.view addSubview:self.tableView];
    
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(handleThemeChanged:)
                                                 name:IrisThemeDidChangeNotification
                                               object:nil];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)handleThemeChanged:(NSNotification *)note {
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    [self.themeSwitch setOn:[IrisTheme sharedTheme].isDarkMode animated:YES];
    [self.tableView reloadData];
}

- (void)dismissSelf {
    [self dismissViewControllerAnimated:YES completion:nil];
}

#pragma mark - Table View

- (NSInteger)numberOfSectionsInTableView:(UITableView *)tableView {
    return 3;
}

- (NSString *)tableView:(UITableView *)tableView titleForHeaderInSection:(NSInteger)section {
    if (section == 0) return @"APPEARANCE";
    if (section == 1) return @"HAKIOS RUNTIME & PERFORMANCE";
    return @"ABOUT";
}

- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section {
    if (section == 0) return 1;
    if (section == 1) return 4;
    return 3;
}

- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)indexPath {
    UITableViewCell *cell = [[UITableViewCell alloc] initWithStyle:UITableViewCellStyleValue1 reuseIdentifier:nil];
    cell.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
    cell.textLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    cell.textLabel.font = [UIFont systemFontOfSize:14 weight:UIFontWeightMedium];
    cell.detailTextLabel.textColor = [[IrisTheme sharedTheme] secondaryTextColor];
    cell.detailTextLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightRegular];
    cell.selectionStyle = UITableViewCellSelectionStyleNone;
    
    if (indexPath.section == 0) {
        cell.textLabel.text = @"Dark Mode";
        self.themeSwitch = [[UISwitch alloc] init];
        self.themeSwitch.onTintColor = [[IrisTheme sharedTheme] accentVioletColor];
        self.themeSwitch.on = [IrisTheme sharedTheme].isDarkMode;
        [self.themeSwitch addTarget:self action:@selector(toggleDarkMode:) forControlEvents:UIControlEventValueChanged];
        cell.accessoryView = self.themeSwitch;
    } else if (indexPath.section == 1) {
        if (indexPath.row == 0) {
            cell.textLabel.text = @"Display Resolution";
            cell.detailTextLabel.text = @"1080 x 2400 (360x800 @3x)";
        } else if (indexPath.row == 1) {
            cell.textLabel.text = @"Target Refresh Rate";
            cell.detailTextLabel.text = @"60 FPS (9.4 ms frame avg)";
        } else if (indexPath.row == 2) {
            cell.textLabel.text = @"Compositor / GPU";
            cell.detailTextLabel.text = @"SpringBoard / Mali Panfrost";
        } else {
            cell.textLabel.text = @"Input Subsystem";
            cell.detailTextLabel.text = @"Melfas MSS100 Touch Driver";
        }
    } else {
        if (indexPath.row == 0) {
            cell.textLabel.text = @"Application";
            cell.detailTextLabel.text = @"Iris Social UI";
        } else if (indexPath.row == 1) {
            cell.textLabel.text = @"Version";
            cell.detailTextLabel.text = @"1.0.0-hakios (Phase 1)";
        } else {
            cell.textLabel.text = @"Platform";
            cell.detailTextLabel.text = @"HakiOS / Samsung Galaxy A51";
        }
    }
    
    return cell;
}

- (void)toggleDarkMode:(UISwitch *)sender {
    [IrisTheme sharedTheme].isDarkMode = sender.isOn;
}

@end
