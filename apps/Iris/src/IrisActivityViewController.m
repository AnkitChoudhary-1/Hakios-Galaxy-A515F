// IrisActivityViewController.m - Activity and notifications screen implementation
#import "IrisActivityViewController.h"
#import "IrisTheme.h"
#import "IrisData.h"
#import "IrisProfileViewController.h"
#import "IrisPostViewerViewController.h"

@interface IrisNotificationCell : UITableViewCell

@property (nonatomic, strong) IrisNotification *notification;
@property (nonatomic, strong) UIImageView *avatarImageView;
@property (nonatomic, strong) UILabel *messageLabel;
@property (nonatomic, strong) UILabel *timeLabel;
@property (nonatomic, strong) UIButton *followButton;
@property (nonatomic, strong) UIImageView *thumbnailImageView;
@property (nonatomic, copy) void (^userTapHandler)(NSString *username);
@property (nonatomic, copy) void (^followToggleHandler)(IrisNotification *notif);
@property (nonatomic, copy) void (^mediaTapHandler)(NSString *imageKey);

- (void)configureWithNotification:(IrisNotification *)notification;
- (void)updateTheme;

@end

@implementation IrisNotificationCell

- (instancetype)initWithStyle:(UITableViewCellStyle)style reuseIdentifier:(NSString *)reuseIdentifier {
    self = [super initWithStyle:style reuseIdentifier:reuseIdentifier];
    if (self) {
        self.selectionStyle = UITableViewCellSelectionStyleNone;
        [self setupSubviews];
    }
    return self;
}

- (void)setupSubviews {
    self.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.contentView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    // Avatar
    self.avatarImageView = [[UIImageView alloc] initWithFrame:CGRectMake(16, 12, 44, 44)];
    self.avatarImageView.layer.cornerRadius = 22.0;
    self.avatarImageView.layer.masksToBounds = YES;
    self.avatarImageView.userInteractionEnabled = YES;
    UITapGestureRecognizer *tapAvatar = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(handleUserTap)];
    [self.avatarImageView addGestureRecognizer:tapAvatar];
    [self.contentView addSubview:self.avatarImageView];
    
    // Message Label
    self.messageLabel = [[UILabel alloc] init];
    self.messageLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightRegular];
    self.messageLabel.numberOfLines = 2;
    self.messageLabel.userInteractionEnabled = YES;
    UITapGestureRecognizer *tapMsg = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(handleUserTap)];
    [self.messageLabel addGestureRecognizer:tapMsg];
    [self.contentView addSubview:self.messageLabel];
    
    // Timestamp
    self.timeLabel = [[UILabel alloc] init];
    self.timeLabel.font = [UIFont systemFontOfSize:11 weight:UIFontWeightRegular];
    [self.contentView addSubview:self.timeLabel];
    
    // Follow button
    self.followButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.followButton.titleLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightSemibold];
    self.followButton.layer.cornerRadius = 6.0;
    [self.followButton addTarget:self action:@selector(handleFollowTap) forControlEvents:UIControlEventTouchUpInside];
    [self.contentView addSubview:self.followButton];
    
    // Media Thumbnail
    self.thumbnailImageView = [[UIImageView alloc] init];
    self.thumbnailImageView.layer.cornerRadius = 6.0;
    self.thumbnailImageView.layer.masksToBounds = YES;
    self.thumbnailImageView.contentMode = UIViewContentModeScaleAspectFill;
    self.thumbnailImageView.userInteractionEnabled = YES;
    UITapGestureRecognizer *tapThumb = [[UITapGestureRecognizer alloc] initWithTarget:self action:@selector(handleMediaTap)];
    [self.thumbnailImageView addGestureRecognizer:tapThumb];
    [self.contentView addSubview:self.thumbnailImageView];
    
    [self updateTheme];
}

- (void)configureWithNotification:(IrisNotification *)notification {
    _notification = notification;
    
    self.avatarImageView.image = [IrisData imageForKey:notification.avatar
                                                  size:CGSizeMake(44, 44)
                                                 title:[notification.username uppercaseString]
                                              subtitle:@""];
    
    // Attributed notification text: bold username + message
    NSString *full = [NSString stringWithFormat:@"%@ %@", notification.username, notification.message];
    NSMutableAttributedString *attr = [[NSMutableAttributedString alloc] initWithString:full];
    [attr addAttribute:NSFontAttributeName value:[UIFont systemFontOfSize:13 weight:UIFontWeightBold] range:NSMakeRange(0, notification.username.length)];
    [attr addAttribute:NSForegroundColorAttributeName value:[[IrisTheme sharedTheme] primaryTextColor] range:NSMakeRange(0, attr.length)];
    self.messageLabel.attributedText = attr;
    
    self.timeLabel.text = notification.timestamp;
    
    // Handle action right element (Follow button vs Post thumbnail)
    if ([notification.type isEqualToString:@"follow"]) {
        self.thumbnailImageView.hidden = YES;
        self.followButton.hidden = NO;
        [self updateFollowButton];
    } else {
        self.followButton.hidden = YES;
        if (notification.thumbnailImageKey.length > 0) {
            self.thumbnailImageView.hidden = NO;
            self.thumbnailImageView.image = [IrisData imageForKey:notification.thumbnailImageKey
                                                             size:CGSizeMake(44, 44)
                                                            title:@""
                                                         subtitle:@""];
        } else {
            self.thumbnailImageView.hidden = YES;
        }
    }
    
    [self updateTheme];
    [self setNeedsLayout];
}

- (void)updateFollowButton {
    if (self.notification.isFollowing) {
        [self.followButton setTitle:@"Following" forState:UIControlStateNormal];
        self.followButton.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
        [self.followButton setTitleColor:[[IrisTheme sharedTheme] primaryTextColor] forState:UIControlStateNormal];
    } else {
        [self.followButton setTitle:@"Follow" forState:UIControlStateNormal];
        self.followButton.backgroundColor = [[IrisTheme sharedTheme] accentVioletColor];
        [self.followButton setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    }
}

- (void)updateTheme {
    self.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.contentView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.timeLabel.textColor = [[IrisTheme sharedTheme] mutedTextColor];
    [self updateFollowButton];
}

- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat w = self.contentView.bounds.size.width;
    CGFloat rightPad = 16.0;
    
    self.avatarImageView.frame = CGRectMake(16, 12, 44, 44);
    
    CGFloat textRight = w - rightPad;
    if (!self.followButton.hidden) {
        CGFloat btnW = 80.0;
        self.followButton.frame = CGRectMake(w - rightPad - btnW, 18, btnW, 32);
        textRight -= (btnW + 12);
    } else if (!self.thumbnailImageView.hidden) {
        CGFloat thumbSize = 44.0;
        self.thumbnailImageView.frame = CGRectMake(w - rightPad - thumbSize, 12, thumbSize, thumbSize);
        textRight -= (thumbSize + 12);
    }
    
    CGFloat textW = textRight - 70;
    CGSize msgSize = [self.messageLabel sizeThatFits:CGSizeMake(textW, CGFLOAT_MAX)];
    self.messageLabel.frame = CGRectMake(70, 12, textW, MIN(msgSize.height, 36));
    self.timeLabel.frame = CGRectMake(70, CGRectGetMaxY(self.messageLabel.frame) + 2, textW, 14);
}

- (void)handleUserTap {
    if (self.userTapHandler) {
        self.userTapHandler(self.notification.username);
    }
}

- (void)handleFollowTap {
    self.notification.isFollowing = !self.notification.isFollowing;
    [[IrisData sharedData] toggleFollowForUsername:self.notification.username];
    [self updateFollowButton];
    if (self.followToggleHandler) {
        self.followToggleHandler(self.notification);
    }
}

- (void)handleMediaTap {
    if (self.mediaTapHandler && self.notification.thumbnailImageKey.length > 0) {
        self.mediaTapHandler(self.notification.thumbnailImageKey);
    }
}

@end

@interface IrisActivityViewController () <UITableViewDataSource, UITableViewDelegate>

@property (nonatomic, strong) UIView *headerView;
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, strong) UITableView *tableView;

@end

@implementation IrisActivityViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    CGFloat topSafe = 36.0;
    CGFloat headerH = topSafe + 50.0;
    
    // Header
    self.headerView = [[UIView alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, headerH)];
    self.headerView.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.headerView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    self.titleLabel = [[UILabel alloc] initWithFrame:CGRectMake(16, topSafe + 8, 200, 32)];
    self.titleLabel.text = @"Activity";
    self.titleLabel.font = [UIFont systemFontOfSize:26 weight:UIFontWeightBold];
    self.titleLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    [self.headerView addSubview:self.titleLabel];
    
    UIView *divider = [[UIView alloc] initWithFrame:CGRectMake(0, headerH - 0.5, self.view.bounds.size.width, 0.5)];
    divider.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    divider.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    [self.headerView addSubview:divider];
    
    [self.view addSubview:self.headerView];
    
    // Table
    CGFloat bottomH = 64.0;
    CGRect tableFrame = CGRectMake(0, headerH, self.view.bounds.size.width, self.view.bounds.size.height - headerH - bottomH);
    self.tableView = [[UITableView alloc] initWithFrame:tableFrame style:UITableViewStylePlain];
    self.tableView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.tableView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.tableView.separatorStyle = UITableViewCellSeparatorStyleNone;
    self.tableView.dataSource = self;
    self.tableView.delegate = self;
    [self.tableView registerClass:[IrisNotificationCell class] forCellReuseIdentifier:@"IrisNotificationCell"];
    [self.view addSubview:self.tableView];
    
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(handleThemeChanged:)
                                                 name:IrisThemeDidChangeNotification
                                               object:nil];
}

- (void)viewWillAppear:(BOOL)animated {
    [super viewWillAppear:animated];
    [self.tableView reloadData];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)handleThemeChanged:(NSNotification *)note {
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.headerView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.titleLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.tableView.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    [self.tableView reloadData];
}

#pragma mark - Table View Data Source

- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section {
    return [IrisData sharedData].notifications.count;
}

- (CGFloat)tableView:(UITableView *)tableView heightForRowAtIndexPath:(NSIndexPath *)indexPath {
    return 68.0;
}

- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)indexPath {
    IrisNotificationCell *cell = [tableView dequeueReusableCellWithIdentifier:@"IrisNotificationCell" forIndexPath:indexPath];
    IrisNotification *n = [IrisData sharedData].notifications[indexPath.row];
    [cell configureWithNotification:n];
    
    __weak typeof(self) weakSelf = self;
    cell.userTapHandler = ^(NSString *username) {
        IrisProfileViewController *profile = [[IrisProfileViewController alloc] initWithUsername:username];
        UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:profile];
        [weakSelf presentViewController:nav animated:YES completion:nil];
    };
    
    cell.mediaTapHandler = ^(NSString *imageKey) {
        IrisPost *targetPost = nil;
        for (IrisPost *p in [IrisData sharedData].posts) {
            if ([p.imageKey isEqualToString:imageKey]) {
                targetPost = p;
                break;
            }
        }
        if (!targetPost) targetPost = [IrisData sharedData].posts.firstObject;
        IrisPostViewerViewController *viewer = [[IrisPostViewerViewController alloc] initWithPost:targetPost];
        viewer.modalPresentationStyle = UIModalPresentationFullScreen;
        [weakSelf presentViewController:viewer animated:YES completion:nil];
    };
    
    return cell;
}

@end
