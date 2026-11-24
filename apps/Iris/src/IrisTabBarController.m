// IrisTabBarController.m - Custom bottom navigation bar implementation
#import "IrisTabBarController.h"
#import "IrisTheme.h"

@interface IrisTabBarController ()

@property (nonatomic, strong) UIView *contentContainerView;
@property (nonatomic, strong) UIView *customTabBar;
@property (nonatomic, strong) UIVisualEffectView *blurView;
@property (nonatomic, strong) UIView *topDivider;
@property (nonatomic, strong) NSMutableArray<UIButton *> *tabButtons;
@property (nonatomic, strong) UIView *activeIndicator;
@property (nonatomic, strong) NSArray<UIViewController *> *viewControllers;

@end

@implementation IrisTabBarController

- (instancetype)initWithViewControllers:(NSArray<UIViewController *> *)viewControllers {
    self = [super init];
    if (self) {
        _viewControllers = viewControllers;
        _selectedTab = IrisTabItemHome;
        _tabButtons = [NSMutableArray array];
    }
    return self;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    // Container for active screen
    self.contentContainerView = [[UIView alloc] initWithFrame:self.view.bounds];
    self.contentContainerView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self.view addSubview:self.contentContainerView];
    
    // Custom floating glass tab bar
    [self setupCustomTabBar];
    
    // Attach initial controller
    [self updateSelectedViewController];
    
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(handleThemeChanged:)
                                                 name:IrisThemeDidChangeNotification
                                               object:nil];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)setupCustomTabBar {
    CGFloat barHeight = 64.0;
    CGFloat bottomInset = self.view.safeAreaInsets.bottom > 0 ? self.view.safeAreaInsets.bottom : 20.0;
    CGRect barFrame = CGRectMake(0, self.view.bounds.size.height - (barHeight + bottomInset), self.view.bounds.size.width, barHeight + bottomInset);
    
    self.customTabBar = [[UIView alloc] initWithFrame:barFrame];
    self.customTabBar.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin;
    self.customTabBar.backgroundColor = [[IrisTheme sharedTheme] glassSurfaceColor];
    
    // Top border line
    self.topDivider = [[UIView alloc] initWithFrame:CGRectMake(0, 0, barFrame.size.width, 0.5)];
    self.topDivider.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.topDivider.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    [self.customTabBar addSubview:self.topDivider];
    
    // Active pill indicator
    self.activeIndicator = [[UIView alloc] initWithFrame:CGRectMake(0, 52, 20, 3)];
    self.activeIndicator.layer.cornerRadius = 1.5;
    self.activeIndicator.backgroundColor = [[IrisTheme sharedTheme] accentVioletColor];
    [self.customTabBar addSubview:self.activeIndicator];
    
    // 5 Tab items
    NSArray *tabIcons = @[@"home", @"explore", @"create", @"activity", @"profile"];
    CGFloat tabWidth = barFrame.size.width / (CGFloat)tabIcons.count;
    
    for (NSInteger i = 0; i < (NSInteger)tabIcons.count; i++) {
        UIButton *btn = [UIButton buttonWithType:UIButtonTypeCustom];
        btn.frame = CGRectMake(i * tabWidth, 4, tabWidth, 48);
        btn.tag = i;
        [btn addTarget:self action:@selector(tabButtonTapped:) forControlEvents:UIControlEventTouchUpInside];
        
        BOOL isSelected = (i == self.selectedTab);
        UIColor *iconColor = isSelected ? [[IrisTheme sharedTheme] primaryTextColor] : [[IrisTheme sharedTheme] mutedTextColor];
        UIImage *icon = [IrisTheme iconNamed:tabIcons[i] size:CGSizeMake(24, 24) color:iconColor filled:isSelected];
        [btn setImage:icon forState:UIControlStateNormal];
        
        [self.customTabBar addSubview:btn];
        [self.tabButtons addObject:btn];
    }
    
    [self.view addSubview:self.customTabBar];
    [self updateIndicatorPositionAnimated:NO];
}

- (void)viewDidLayoutSubviews {
    [super viewDidLayoutSubviews];
    CGFloat bottomInset = self.view.safeAreaInsets.bottom > 0 ? self.view.safeAreaInsets.bottom : 20.0;
    CGFloat barHeight = 64.0;
    self.customTabBar.frame = CGRectMake(0, self.view.bounds.size.height - (barHeight + bottomInset), self.view.bounds.size.width, barHeight + bottomInset);
    
    CGFloat tabWidth = self.view.bounds.size.width / (CGFloat)self.tabButtons.count;
    for (NSInteger i = 0; i < (NSInteger)self.tabButtons.count; i++) {
        self.tabButtons[i].frame = CGRectMake(i * tabWidth, 4, tabWidth, 48);
    }
    [self updateIndicatorPositionAnimated:NO];
}

- (void)tabButtonTapped:(UIButton *)sender {
    [self switchToTab:(IrisTabItem)sender.tag];
}

- (void)switchToTab:(IrisTabItem)tab {
    if (tab < 0 || tab >= (IrisTabItem)self.viewControllers.count) return;
    if (_selectedTab == tab) return;
    
    _selectedTab = tab;
    [self updateSelectedViewController];
    [self updateTabBarButtons];
    [self updateIndicatorPositionAnimated:YES];
}

- (void)updateSelectedViewController {
    if (self.selectedTab >= (IrisTabItem)self.viewControllers.count) return;
    
    UIViewController *nextVC = self.viewControllers[self.selectedTab];
    if (self.childViewControllers.count > 0 && self.childViewControllers.firstObject == nextVC) {
        return;
    }
    
    for (UIViewController *child in self.childViewControllers) {
        [child willMoveToParentViewController:nil];
        [child.view removeFromSuperview];
        [child removeFromParentViewController];
    }
    
    [self addChildViewController:nextVC];
    nextVC.view.frame = self.contentContainerView.bounds;
    nextVC.view.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [self.contentContainerView addSubview:nextVC.view];
    [nextVC didMoveToParentViewController:self];
}

- (void)updateTabBarButtons {
    NSArray *tabIcons = @[@"home", @"explore", @"create", @"activity", @"profile"];
    for (NSInteger i = 0; i < (NSInteger)self.tabButtons.count; i++) {
        UIButton *btn = self.tabButtons[i];
        BOOL isSelected = (i == self.selectedTab);
        UIColor *iconColor = isSelected ? [[IrisTheme sharedTheme] primaryTextColor] : [[IrisTheme sharedTheme] mutedTextColor];
        UIImage *icon = [IrisTheme iconNamed:tabIcons[i] size:CGSizeMake(24, 24) color:iconColor filled:isSelected];
        [btn setImage:icon forState:UIControlStateNormal];
    }
}

- (void)updateIndicatorPositionAnimated:(BOOL)animated {
    if (self.tabButtons.count == 0) return;
    CGFloat tabWidth = self.customTabBar.bounds.size.width / (CGFloat)self.tabButtons.count;
    CGFloat centerX = (self.selectedTab * tabWidth) + (tabWidth / 2.0);
    CGRect targetFrame = CGRectMake(centerX - 12, 52, 24, 3);
    
    if (animated) {
        [UIView animateWithDuration:0.25 delay:0 options:UIViewAnimationOptionCurveEaseInOut animations:^{
            self.activeIndicator.frame = targetFrame;
        } completion:nil];
    } else {
        self.activeIndicator.frame = targetFrame;
    }
}

- (void)handleThemeChanged:(NSNotification *)note {
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.customTabBar.backgroundColor = [[IrisTheme sharedTheme] glassSurfaceColor];
    self.topDivider.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    self.activeIndicator.backgroundColor = [[IrisTheme sharedTheme] accentVioletColor];
    [self updateTabBarButtons];
}

@end
