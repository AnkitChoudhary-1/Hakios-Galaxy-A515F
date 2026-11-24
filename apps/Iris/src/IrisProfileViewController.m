// IrisProfileViewController.m - User profile implementation
#import "IrisProfileViewController.h"
#import "IrisTheme.h"
#import "IrisData.h"
#import "IrisSettingsViewController.h"
#import "IrisPostViewerViewController.h"

@interface IrisProfileViewController () <UIScrollViewDelegate>

@property (nonatomic, strong) IrisProfile *profile;
@property (nonatomic, strong) UIScrollView *scrollView;

// Top Nav
@property (nonatomic, strong) UIView *topBar;
@property (nonatomic, strong) UILabel *navTitleLabel;
@property (nonatomic, strong) UIButton *backButton;
@property (nonatomic, strong) UIButton *settingsButton;

// Profile Header
@property (nonatomic, strong) UIView *headerContainer;
@property (nonatomic, strong) UIImageView *avatarImageView;
@property (nonatomic, strong) UILabel *postsCountLabel;
@property (nonatomic, strong) UILabel *followersCountLabel;
@property (nonatomic, strong) UILabel *followingCountLabel;
@property (nonatomic, strong) UILabel *displayNameLabel;
@property (nonatomic, strong) UILabel *bioLabel;
@property (nonatomic, strong) UIButton *websiteButton;

// Actions
@property (nonatomic, strong) UIButton *actionPrimaryButton;
@property (nonatomic, strong) UIButton *actionSecondaryButton;

// Tabs
@property (nonatomic, strong) UIView *tabsContainer;
@property (nonatomic, strong) UIButton *gridTabButton;
@property (nonatomic, strong) UIButton *reelsTabButton;
@property (nonatomic, strong) UIButton *tagsTabButton;
@property (nonatomic, strong) UIView *tabIndicator;
@property (nonatomic, assign) NSInteger selectedTab; // 0: grid, 1: reels, 2: tags

// Grid
@property (nonatomic, strong) UIView *gridContainer;
@property (nonatomic, strong) NSMutableArray<UIImageView *> *gridImageViews;

@end

@implementation IrisProfileViewController

- (instancetype)initWithUsername:(NSString *)username {
    self = [super init];
    if (self) {
        _username = [username copy];
        _selectedTab = 0;
        _gridImageViews = [NSMutableArray array];
    }
    return self;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    [self loadProfileData];
    [self setupTopBar];
    [self setupScrollView];
    [self setupProfileHeader];
    [self setupTabsAndGrid];
    
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(handleThemeChanged:)
                                                 name:IrisThemeDidChangeNotification
                                               object:nil];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)loadProfileData {
    if (!self.username || self.username.length == 0) {
        self.username = [IrisData sharedData].currentUserProfile.username;
    }
    self.profile = [IrisData sharedData].profiles[self.username];
    if (!self.profile) {
        self.profile = [IrisData sharedData].currentUserProfile;
    }
}

- (void)setupTopBar {
    CGFloat topSafe = 36.0;
    CGFloat barH = topSafe + 44.0;
    
    self.topBar = [[UIView alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, barH)];
    self.topBar.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.topBar.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    // Back button (shown if pushed or modal)
    self.backButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.backButton.frame = CGRectMake(12, topSafe + 4, 36, 36);
    [self.backButton setImage:[IrisTheme iconNamed:@"back" size:CGSizeMake(22, 22) color:[[IrisTheme sharedTheme] primaryTextColor] filled:NO] forState:UIControlStateNormal];
    [self.backButton addTarget:self action:@selector(handleBackTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.topBar addSubview:self.backButton];
    
    BOOL isModalOrPushed = (self.navigationController.viewControllers.count > 1 || self.presentingViewController != nil);
    self.backButton.hidden = !isModalOrPushed;
    
    // Username title
    self.navTitleLabel = [[UILabel alloc] initWithFrame:CGRectMake(56, topSafe + 6, self.view.bounds.size.width - 112, 32)];
    self.navTitleLabel.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.navTitleLabel.text = self.profile.username;
    self.navTitleLabel.font = [UIFont systemFontOfSize:17 weight:UIFontWeightBold];
    self.navTitleLabel.textAlignment = NSTextAlignmentCenter;
    self.navTitleLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    [self.topBar addSubview:self.navTitleLabel];
    
    // Settings button (only on current user profile)
    BOOL isCurrentUser = [self.profile.username isEqualToString:[IrisData sharedData].currentUserProfile.username];
    self.settingsButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.settingsButton.frame = CGRectMake(self.view.bounds.size.width - 48, topSafe + 4, 36, 36);
    self.settingsButton.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin;
    [self.settingsButton setImage:[IrisTheme iconNamed:@"settings" size:CGSizeMake(22, 22) color:[[IrisTheme sharedTheme] primaryTextColor] filled:NO] forState:UIControlStateNormal];
    [self.settingsButton addTarget:self action:@selector(handleSettingsTapped) forControlEvents:UIControlEventTouchUpInside];
    self.settingsButton.hidden = !isCurrentUser;
    [self.topBar addSubview:self.settingsButton];
    
    [self.view addSubview:self.topBar];
}

- (void)setupScrollView {
    CGFloat topBarH = 80.0;
    CGFloat bottomH = 64.0;
    self.scrollView = [[UIScrollView alloc] initWithFrame:CGRectMake(0, topBarH, self.view.bounds.size.width, self.view.bounds.size.height - topBarH - bottomH)];
    self.scrollView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.scrollView.alwaysBounceVertical = YES;
    self.scrollView.showsVerticalScrollIndicator = NO;
    [self.view addSubview:self.scrollView];
}

- (void)setupProfileHeader {
    self.headerContainer = [[UIView alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, 240)];
    self.headerContainer.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    
    CGFloat w = self.view.bounds.size.width;
    CGFloat avatarSize = 76.0;
    
    // Avatar
    self.avatarImageView = [[UIImageView alloc] initWithFrame:CGRectMake(16, 12, avatarSize, avatarSize)];
    self.avatarImageView.layer.cornerRadius = avatarSize / 2.0;
    self.avatarImageView.layer.masksToBounds = YES;
    self.avatarImageView.layer.borderWidth = 2.0;
    self.avatarImageView.layer.borderColor = [[IrisTheme sharedTheme] accentVioletColor].CGColor;
    self.avatarImageView.image = [IrisData imageForKey:self.profile.avatar
                                                  size:CGSizeMake(avatarSize, avatarSize)
                                                 title:[self.profile.username uppercaseString]
                                              subtitle:@""];
    [self.headerContainer addSubview:self.avatarImageView];
    
    // Stat counters
    CGFloat statsLeft = 16 + avatarSize + 12;
    CGFloat statColW = (w - statsLeft - 16) / 3.0;
    
    self.postsCountLabel = [self createStatViewWithTitle:@"Posts" value:@(self.profile.postsCount) frame:CGRectMake(statsLeft, 22, statColW, 44)];
    self.followersCountLabel = [self createStatViewWithTitle:@"Followers" value:@(self.profile.followersCount) frame:CGRectMake(statsLeft + statColW, 22, statColW, 44)];
    self.followingCountLabel = [self createStatViewWithTitle:@"Following" value:@(self.profile.followingCount) frame:CGRectMake(statsLeft + statColW * 2, 22, statColW, 44)];
    
    // Display Name
    self.displayNameLabel = [[UILabel alloc] initWithFrame:CGRectMake(16, 96, w - 32, 20)];
    self.displayNameLabel.font = [UIFont systemFontOfSize:14 weight:UIFontWeightBold];
    self.displayNameLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.displayNameLabel.text = self.profile.displayName;
    [self.headerContainer addSubview:self.displayNameLabel];
    
    // Bio
    self.bioLabel = [[UILabel alloc] initWithFrame:CGRectMake(16, 118, w - 32, 36)];
    self.bioLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightRegular];
    self.bioLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.bioLabel.numberOfLines = 0;
    self.bioLabel.text = self.profile.bio;
    [self.headerContainer addSubview:self.bioLabel];
    
    // Website
    self.websiteButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.websiteButton.frame = CGRectMake(16, 156, w - 32, 18);
    self.websiteButton.contentHorizontalAlignment = UIControlContentHorizontalAlignmentLeft;
    self.websiteButton.titleLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightMedium];
    [self.websiteButton setTitle:[NSString stringWithFormat:@"🔗 %@", self.profile.website] forState:UIControlStateNormal];
    [self.websiteButton setTitleColor:[[IrisTheme sharedTheme] accentVioletColor] forState:UIControlStateNormal];
    [self.headerContainer addSubview:self.websiteButton];
    
    // Action buttons
    CGFloat btnW = (w - 32 - 10) / 2.0;
    self.actionPrimaryButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.actionPrimaryButton.frame = CGRectMake(16, 182, btnW, 36);
    self.actionPrimaryButton.layer.cornerRadius = 8.0;
    self.actionPrimaryButton.titleLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightSemibold];
    [self.actionPrimaryButton addTarget:self action:@selector(primaryActionTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.headerContainer addSubview:self.actionPrimaryButton];
    
    self.actionSecondaryButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.actionSecondaryButton.frame = CGRectMake(16 + btnW + 10, 182, btnW, 36);
    self.actionSecondaryButton.layer.cornerRadius = 8.0;
    self.actionSecondaryButton.titleLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightSemibold];
    [self.actionSecondaryButton addTarget:self action:@selector(secondaryActionTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.headerContainer addSubview:self.actionSecondaryButton];
    
    [self updateActionButtons];
    [self.scrollView addSubview:self.headerContainer];
}

- (UILabel *)createStatViewWithTitle:(NSString *)title value:(NSNumber *)value frame:(CGRect)frame {
    UIView *statView = [[UIView alloc] initWithFrame:frame];
    
    UILabel *valLbl = [[UILabel alloc] initWithFrame:CGRectMake(0, 0, frame.size.width, 22)];
    valLbl.font = [UIFont systemFontOfSize:16 weight:UIFontWeightBold];
    valLbl.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    valLbl.textAlignment = NSTextAlignmentCenter;
    
    NSInteger num = [value integerValue];
    if (num >= 1000) {
        valLbl.text = [NSString stringWithFormat:@"%.1fk", num / 1000.0];
    } else {
        valLbl.text = [NSString stringWithFormat:@"%ld", (long)num];
    }
    [statView addSubview:valLbl];
    
    UILabel *titleLbl = [[UILabel alloc] initWithFrame:CGRectMake(0, 22, frame.size.width, 16)];
    titleLbl.font = [UIFont systemFontOfSize:12 weight:UIFontWeightRegular];
    titleLbl.textColor = [[IrisTheme sharedTheme] secondaryTextColor];
    titleLbl.textAlignment = NSTextAlignmentCenter;
    titleLbl.text = title;
    [statView addSubview:titleLbl];
    
    [self.headerContainer addSubview:statView];
    return valLbl;
}

- (void)updateActionButtons {
    BOOL isCurrentUser = [self.profile.username isEqualToString:[IrisData sharedData].currentUserProfile.username];
    if (isCurrentUser) {
        [self.actionPrimaryButton setTitle:@"Edit Profile" forState:UIControlStateNormal];
        self.actionPrimaryButton.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
        [self.actionPrimaryButton setTitleColor:[[IrisTheme sharedTheme] primaryTextColor] forState:UIControlStateNormal];
        
        [self.actionSecondaryButton setTitle:@"Share Profile" forState:UIControlStateNormal];
        self.actionSecondaryButton.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
        [self.actionSecondaryButton setTitleColor:[[IrisTheme sharedTheme] primaryTextColor] forState:UIControlStateNormal];
    } else {
        if (self.profile.isFollowing) {
            [self.actionPrimaryButton setTitle:@"Following" forState:UIControlStateNormal];
            self.actionPrimaryButton.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
            [self.actionPrimaryButton setTitleColor:[[IrisTheme sharedTheme] primaryTextColor] forState:UIControlStateNormal];
        } else {
            [self.actionPrimaryButton setTitle:@"Follow" forState:UIControlStateNormal];
            self.actionPrimaryButton.backgroundColor = [[IrisTheme sharedTheme] accentVioletColor];
            [self.actionPrimaryButton setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
        }
        
        [self.actionSecondaryButton setTitle:@"Message" forState:UIControlStateNormal];
        self.actionSecondaryButton.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
        [self.actionSecondaryButton setTitleColor:[[IrisTheme sharedTheme] primaryTextColor] forState:UIControlStateNormal];
    }
}

- (void)setupTabsAndGrid {
    CGFloat w = self.view.bounds.size.width;
    CGFloat y = 230.0;
    
    // Tab Bar
    self.tabsContainer = [[UIView alloc] initWithFrame:CGRectMake(0, y, w, 44)];
    self.tabsContainer.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    UIView *topLine = [[UIView alloc] initWithFrame:CGRectMake(0, 0, w, 0.5)];
    topLine.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    [self.tabsContainer addSubview:topLine];
    
    CGFloat tabW = w / 3.0;
    self.gridTabButton = [self createTabButtonWithIcon:@"grid" tag:0 x:0 w:tabW];
    self.reelsTabButton = [self createTabButtonWithIcon:@"play" tag:1 x:tabW w:tabW];
    self.tagsTabButton = [self createTabButtonWithIcon:@"tag" tag:2 x:tabW * 2 w:tabW];
    
    self.tabIndicator = [[UIView alloc] initWithFrame:CGRectMake(tabW / 2.0 - 24, 41, 48, 2.5)];
    self.tabIndicator.backgroundColor = [[IrisTheme sharedTheme] primaryTextColor];
    [self.tabsContainer addSubview:self.tabIndicator];
    
    [self.scrollView addSubview:self.tabsContainer];
    
    // Grid Container
    y += 44.0;
    self.gridContainer = [[UIView alloc] initWithFrame:CGRectMake(0, y, w, 400)];
    [self.scrollView addSubview:self.gridContainer];
    
    [self renderGrid];
}

- (UIButton *)createTabButtonWithIcon:(NSString *)icon tag:(NSInteger)tag x:(CGFloat)x w:(CGFloat)w {
    UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
    btn.frame = CGRectMake(x, 0, w, 44);
    btn.tag = tag;
    [btn addTarget:self action:@selector(tabTapped:) forControlEvents:UIControlEventTouchUpInside];
    
    UIColor *col = (tag == self.selectedTab) ? [[IrisTheme sharedTheme] primaryTextColor] : [[IrisTheme sharedTheme] mutedTextColor];
    [btn setImage:[IrisTheme iconNamed:icon size:CGSizeMake(20, 20) color:col filled:NO] forState:UIControlStateNormal];
    [self.tabsContainer addSubview:btn];
    return btn;
}

- (void)tabTapped:(UIButton *)sender {
    self.selectedTab = sender.tag;
    
    CGFloat tabW = self.view.bounds.size.width / 3.0;
    [UIView animateWithDuration:0.2 animations:^{
        self.tabIndicator.frame = CGRectMake(self.selectedTab * tabW + tabW / 2.0 - 24, 41, 48, 2.5);
    }];
    
    [self renderGrid];
}

- (void)renderGrid {
    for (UIView *v in self.gridImageViews) {
        [v removeFromSuperview];
    }
    [self.gridImageViews removeAllObjects];
    
    CGFloat w = self.view.bounds.size.width;
    CGFloat spacing = 2.0;
    CGFloat itemSize = (w - spacing * 2.0) / 3.0;
    
    NSArray<NSString *> *images = self.profile.postImages;
    if (images.count < 9) {
        images = @[@"post_arch1", @"post_neon1", @"post_nature1", @"post_street1", @"post_travel1", @"post_coffee1", @"post_mountain1", @"post_portrait1", @"post_minimal1"];
    }
    
    for (NSInteger i = 0; i < (NSInteger)images.count; i++) {
        NSInteger row = i / 3;
        NSInteger col = i % 3;
        
        CGFloat x = col * (itemSize + spacing);
        CGFloat y = row * (itemSize + spacing);
        
        UIImageView *imgView = [[UIImageView alloc] initWithFrame:CGRectMake(x, y, itemSize, itemSize)];
        imgView.contentMode = UIViewContentModeScaleAspectFill;
        imgView.layer.masksToBounds = YES;
        imgView.userInteractionEnabled = YES;
        imgView.tag = i;
        
        NSString *imgKey = images[i];
        imgView.image = [IrisData imageForKey:imgKey
                                         size:CGSizeMake(itemSize, itemSize)
                                        title:@""
                                     subtitle:@""];
        
        UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(gridItemTapped:)];
        [imgView addGestureRecognizer:tap];
        
        [self.gridContainer addSubview:imgView];
        [self.gridImageViews addObject:imgView];
    }
    
    NSInteger totalRows = (images.count + 2) / 3;
    CGFloat gridH = totalRows * (itemSize + spacing) + 40.0;
    self.gridContainer.frame = CGRectMake(0, self.gridContainer.frame.origin.y, w, gridH);
    self.scrollView.contentSize = CGSizeMake(w, CGRectGetMaxY(self.gridContainer.frame));
}

- (void)gridItemTapped:(UITapGestureRecognizer *)gesture {
    NSInteger idx = gesture.view.tag;
    IrisPost *post = nil;
    if (idx < (NSInteger)[IrisData sharedData].posts.count) {
        post = [IrisData sharedData].posts[idx];
    } else {
        post = [IrisData sharedData].posts.firstObject;
    }
    
    IrisPostViewerViewController *viewer = [[IrisPostViewerViewController alloc] initWithPost:post];
    viewer.modalPresentationStyle = UIModalPresentationFullScreen;
    [self presentViewController:viewer animated:YES completion:nil];
}

- (void)primaryActionTapped {
    BOOL isCurrentUser = [self.profile.username isEqualToString:[IrisData sharedData].currentUserProfile.username];
    if (isCurrentUser) {
        UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Edit Profile"
                                                                       message:@"Update your display name, bio, and portfolio link."
                                                                preferredStyle:UIAlertControllerStyleAlert];
        [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
            textField.text = self.profile.displayName;
            textField.placeholder = @"Display Name";
        }];
        [alert addTextFieldWithConfigurationHandler:^(UITextField * _Nonnull textField) {
            textField.text = self.profile.bio;
            textField.placeholder = @"Bio";
        }];
        [alert addAction:[UIAlertAction actionWithTitle:@"Save" style:UIAlertActionStyleDefault handler:^(UIAlertAction * _Nonnull action) {
            NSString *newName = alert.textFields[0].text;
            NSString *newBio = alert.textFields[1].text;
            if (newName.length > 0) self.profile.displayName = newName;
            if (newBio.length > 0) self.profile.bio = newBio;
            self.displayNameLabel.text = self.profile.displayName;
            self.bioLabel.text = self.profile.bio;
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
        [self presentViewController:alert animated:YES completion:nil];
    } else {
        [[IrisData sharedData] toggleFollowForUsername:self.profile.username];
        NSInteger num = self.profile.followersCount;
        if (num >= 1000) {
            self.followersCountLabel.text = [NSString stringWithFormat:@"%.1fk", num / 1000.0];
        } else {
            self.followersCountLabel.text = [NSString stringWithFormat:@"%ld", (long)num];
        }
        [self updateActionButtons];
    }
}

- (void)secondaryActionTapped {
    BOOL isCurrentUser = [self.profile.username isEqualToString:[IrisData sharedData].currentUserProfile.username];
    if (isCurrentUser) {
        UIPasteboard.generalPasteboard.string = [NSString stringWithFormat:@"https://iris.social/@%@", self.profile.username];
        UIAlertController *toast = [UIAlertController alertControllerWithTitle:@"Profile Link Copied"
                                                                       message:@"Link copied to clipboard!"
                                                                preferredStyle:UIAlertControllerStyleAlert];
        [toast addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
        [self presentViewController:toast animated:YES completion:nil];
    } else {
        UIAlertController *toast = [UIAlertController alertControllerWithTitle:[NSString stringWithFormat:@"Message @%@", self.profile.username]
                                                                       message:@"Direct messaging channel will open in Phase 2."
                                                                preferredStyle:UIAlertControllerStyleAlert];
        [toast addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
        [self presentViewController:toast animated:YES completion:nil];
    }
}

- (void)handleBackTapped {
    if (self.navigationController.viewControllers.count > 1) {
        [self.navigationController popViewControllerAnimated:YES];
    } else {
        [self dismissViewControllerAnimated:YES completion:nil];
    }
}

- (void)handleSettingsTapped {
    IrisSettingsViewController *settingsVC = [[IrisSettingsViewController alloc] init];
    UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:settingsVC];
    [self presentViewController:nav animated:YES completion:nil];
}

- (void)handleThemeChanged:(NSNotification *)note {
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.topBar.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.navTitleLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.displayNameLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.bioLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.tabsContainer.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    [self updateActionButtons];
    [self renderGrid];
}

@end
