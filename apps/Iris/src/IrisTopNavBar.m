// IrisTopNavBar.m - Top navigation bar implementation
#import "IrisTopNavBar.h"
#import "IrisTheme.h"

@interface IrisTopNavBar ()

@property (nonatomic, strong) UILabel *brandLabel;
@property (nonatomic, strong) UIView *brandDot;
@property (nonatomic, strong) UIButton *themeButton;
@property (nonatomic, strong) UIButton *notificationsButton;
@property (nonatomic, strong) UIButton *messagesButton;
@property (nonatomic, strong) UIView *bottomDivider;

@end

@implementation IrisTopNavBar

- (instancetype)initWithFrame:(CGRect)frame {
    self = [super initWithFrame:frame];
    if (self) {
        [self setupSubviews];
    }
    return self;
}

- (void)setupSubviews {
    self.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    // Iris brand wordmark
    self.brandLabel = [[UILabel alloc] init];
    self.brandLabel.text = @"Iris";
    self.brandLabel.font = [UIFont systemFontOfSize:26 weight:UIFontWeightBold];
    self.brandLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    [self.brandLabel sizeToFit];
    [self addSubview:self.brandLabel];
    
    // Gradient accent dot next to Iris wordmark
    self.brandDot = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 7, 7)];
    self.brandDot.layer.cornerRadius = 3.5;
    self.brandDot.backgroundColor = [[IrisTheme sharedTheme] accentVioletColor];
    [self addSubview:self.brandDot];
    
    // Action buttons on right: Theme toggle, Notifications, Messages
    self.themeButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.themeButton addTarget:self action:@selector(themeTapped:) forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:self.themeButton];
    
    self.notificationsButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.notificationsButton addTarget:self action:@selector(notificationsTapped:) forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:self.notificationsButton];
    
    self.messagesButton = [UIButton buttonWithType:UIButtonTypeCustom];
    [self.messagesButton addTarget:self action:@selector(messagesTapped:) forControlEvents:UIControlEventTouchUpInside];
    [self addSubview:self.messagesButton];
    
    self.bottomDivider = [[UIView alloc] initWithFrame:CGRectMake(0, self.bounds.size.height - 0.5, self.bounds.size.width, 0.5)];
    self.bottomDivider.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    self.bottomDivider.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin;
    [self addSubview:self.bottomDivider];
    
    [self updateTheme];
}

- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat topSafe = 0;
    if (@available(iOS 11.0, *)) {
        topSafe = self.safeAreaInsets.top;
    }
    CGFloat contentY = topSafe > 0 ? topSafe + 6 : 28;
    
    self.brandLabel.frame = CGRectMake(16, contentY, self.brandLabel.bounds.size.width, 32);
    self.brandDot.frame = CGRectMake(CGRectGetMaxX(self.brandLabel.frame) + 3, contentY + 7, 7, 7);
    
    CGFloat btnSize = 36.0;
    CGFloat rightX = self.bounds.size.width - 16;
    
    self.messagesButton.frame = CGRectMake(rightX - btnSize, contentY, btnSize, btnSize);
    rightX -= (btnSize + 8);
    self.notificationsButton.frame = CGRectMake(rightX - btnSize, contentY, btnSize, btnSize);
    rightX -= (btnSize + 8);
    self.themeButton.frame = CGRectMake(rightX - btnSize, contentY, btnSize, btnSize);
}

- (void)updateTheme {
    self.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.brandLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.bottomDivider.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    
    UIColor *iconColor = [[IrisTheme sharedTheme] primaryTextColor];
    
    NSString *themeIcon = [IrisTheme sharedTheme].isDarkMode ? @"sun" : @"moon";
    [self.themeButton setImage:[IrisTheme iconNamed:themeIcon size:CGSizeMake(22, 22) color:iconColor filled:NO] forState:UIControlStateNormal];
    [self.notificationsButton setImage:[IrisTheme iconNamed:@"notifications" size:CGSizeMake(22, 22) color:iconColor filled:NO] forState:UIControlStateNormal];
    [self.messagesButton setImage:[IrisTheme iconNamed:@"messages" size:CGSizeMake(22, 22) color:iconColor filled:NO] forState:UIControlStateNormal];
}

- (void)themeTapped:(id)sender {
    if ([self.delegate respondsToSelector:@selector(topNavBarDidTapThemeToggle)]) {
        [self.delegate topNavBarDidTapThemeToggle];
    }
}

- (void)notificationsTapped:(id)sender {
    if ([self.delegate respondsToSelector:@selector(topNavBarDidTapNotifications)]) {
        [self.delegate topNavBarDidTapNotifications];
    }
}

- (void)messagesTapped:(id)sender {
    if ([self.delegate respondsToSelector:@selector(topNavBarDidTapMessages)]) {
        [self.delegate topNavBarDidTapMessages];
    }
}

@end
